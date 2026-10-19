import base64
import tomllib
from pathlib import Path

import requests
from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent

KEY_NAMES = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'deepseek': 'DEEPSEEK_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
}

OPENROUTER_URL = "https://openrouter.ai/api/v1"


def read_api_keys(file_path):
    keys = {}
    try:
        with open(file_path, 'r') as file:
            for line in file:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                keys[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return keys


def load_models(file_path):
    with open(file_path, 'rb') as file:
        config = tomllib.load(file)
    models = config['models']
    commands = {}
    for name, entry in models.items():
        commands[name] = name
        for alias in entry.get('aliases', []):
            commands[alias] = name
    default = config.get('default', next(iter(models)))
    return default, models, commands, config.get('prefer_openrouter', False)


api_keys = read_api_keys(BASE_DIR / 'keys.txt')
DEFAULT_MODEL, MODELS, MODEL_COMMANDS, PREFER_OPENROUTER = load_models(BASE_DIR / 'models.toml')

# System prompt text
with open(BASE_DIR / 'system_prompt.txt', 'r') as file:
    # system_prompt = file.read()
    system_prompt = ''


def has_key(provider):
    key = api_keys.get(KEY_NAMES[provider], '')
    return bool(key) and not key.startswith('your')


def get_key(provider):
    if not has_key(provider):
        raise ValueError(f"{KEY_NAMES[provider]} is missing from keys.txt")
    return api_keys[KEY_NAMES[provider]]


_openrouter_models = None


def openrouter_model_exists(model_id):
    """Checks OpenRouter's public model list. Returns True if the list can't be fetched."""
    global _openrouter_models
    if _openrouter_models is None:
        try:
            response = requests.get(f"{OPENROUTER_URL}/models", timeout=10)
            response.raise_for_status()
            _openrouter_models = {m['id'] for m in response.json()['data']}
        except Exception:
            return True
    return model_id in _openrouter_models


def resolve_model(model):
    """Returns (provider, model_id) for a models.toml name or an OpenRouter model ID."""
    if model not in MODELS:
        return 'openrouter', model

    entry = MODELS[model]
    provider = entry['provider']
    openrouter_id = entry.get('openrouter')
    if provider == 'ollama' or provider == 'openrouter' or not openrouter_id:
        return provider, entry['model']

    if has_key('openrouter') and (PREFER_OPENROUTER or not has_key(provider)):
        return 'openrouter', openrouter_id
    if not has_key(provider):
        raise ValueError(f"Add {KEY_NAMES[provider]} or OPENROUTER_API_KEY to keys.txt")
    return provider, entry['model']


# Each query_* function is a generator of (kind, value) events:
#   (THINKING, None) while the model is reasoning
#   (TEXT, "...")    for each piece of the answer
THINKING = 'thinking'
TEXT = 'text'


# Function to query Claude
def query_anthropic(model_id, text, image_base64=None):
    client = Anthropic(api_key=get_key('anthropic'))

    content = [{"type": "text", "text": text}]
    if image_base64:
        content.insert(0, {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": image_base64
            }
        })

    with client.beta.messages.stream(
        model=model_id,
        max_tokens=64000,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
        # If a safety classifier declines, retry on a fallback model in the same call
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        for event in stream:
            if event.type == "content_block_start" and event.content_block.type in ("thinking", "redacted_thinking"):
                yield THINKING, None
            elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                yield TEXT, event.delta.text
        response = stream.get_final_message()

    if response.stop_reason == "refusal":
        yield TEXT, "Claude declined to answer this request."


# Function to query OpenAI (Responses API)
def query_openai(model_id, text, image_base64=None):
    client = OpenAI(api_key=get_key('openai'))

    content = [{"type": "input_text", "text": text}]
    if image_base64:
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{image_base64}"
        })

    stream = client.responses.create(
        model=model_id,
        instructions=system_prompt or None,
        input=[{"role": "user", "content": content}],
        stream=True,
    )
    for event in stream:
        if event.type == "response.output_item.added" and event.item.type == "reasoning":
            yield THINKING, None
        elif event.type == "response.output_text.delta":
            yield TEXT, event.delta
        elif event.type == "response.failed":
            raise RuntimeError(event.response.error.message if event.response.error else "response failed")


# Shared streaming for OpenAI-compatible Chat Completions APIs (DeepSeek, OpenRouter)
def stream_chat_completions(client, model_id, text, image_base64=None, **kwargs):
    content = [{"type": "text", "text": text}]
    if image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    messages = [{"role": "user", "content": content}]
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    stream = client.chat.completions.create(model=model_id, messages=messages, stream=True, **kwargs)
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        # DeepSeek sends reasoning_content; OpenRouter sends reasoning / reasoning_details
        if (getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
                or getattr(delta, 'reasoning_details', None)):
            yield THINKING, None
        if delta.content:
            yield TEXT, delta.content


# Function to query DeepSeek (OpenAI-compatible Chat Completions API)
def query_deepseek(model_id, text, image_base64=None):
    client = OpenAI(api_key=get_key('deepseek'), base_url="https://api.deepseek.com")
    yield from stream_chat_completions(client, model_id, text, image_base64)


# Function to query any model on OpenRouter (OpenAI-compatible Chat Completions API)
def query_openrouter(model_id, text, image_base64=None):
    client = OpenAI(api_key=get_key('openrouter'), base_url=OPENROUTER_URL)
    yield from stream_chat_completions(
        client, model_id, text, image_base64,
        extra_headers={
            "HTTP-Referer": "https://github.com/olyaiy/TypeGPT",
            "X-OpenRouter-Title": "TypeGPT",
        },
    )


# Function to query Gemini
def query_gemini(model_id, text, image_base64=None):
    client = genai.Client(api_key=get_key('gemini'))

    contents = [text]
    if image_base64:
        contents.append(types.Part.from_bytes(
            data=base64.b64decode(image_base64),
            mime_type="image/png"
        ))

    stream = client.models.generate_content_stream(
        model=model_id,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt or None,
            # Sends thought summaries, which tell us when Gemini is thinking
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        ),
    )
    for chunk in stream:
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        for part in chunk.candidates[0].content.parts or []:
            if part.thought:
                yield THINKING, None
            elif part.text:
                yield TEXT, part.text


# Function to query a local Ollama model
def query_ollama(model_id, text, image_base64=None):
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": text
            }
        ],
        "stream": False
    }

    if image_base64:
        payload["messages"][1]["images"] = [image_base64]

    response = requests.post(url, json=payload)
    response.raise_for_status()
    yield TEXT, response.json()['message']['content']


PROVIDERS = {
    'anthropic': query_anthropic,
    'openai': query_openai,
    'deepseek': query_deepseek,
    'gemini': query_gemini,
    'openrouter': query_openrouter,
    'ollama': query_ollama,
}


# main function: yields (THINKING, None) and (TEXT, str) events; errors come back as text
def api_stream(model, text, image_base64=None):
    try:
        provider, model_id = resolve_model(model)
    except ValueError as e:
        yield TEXT, f"Error: {e}"
        return

    if provider not in PROVIDERS:
        yield TEXT, f"Error: Unknown provider '{provider}' in models.toml"
        return

    try:
        yield from PROVIDERS[provider](model_id, text, image_base64)
    except Exception as e:
        yield TEXT, f"Error in {model} ({provider}: {model_id}) API call: {e}"


def api_call(model, text, image_base64=None):
    return ''.join(value for kind, value in api_stream(model, text, image_base64) if kind == TEXT)
