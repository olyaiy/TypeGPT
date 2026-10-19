import base64
import datetime
import logging
import tomllib
from pathlib import Path

import requests
from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
log = logging.getLogger('typegpt')

KEY_NAMES = {
    'anthropic': 'ANTHROPIC_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'deepseek': 'DEEPSEEK_API_KEY',
    'gemini': 'GEMINI_API_KEY',
    'openrouter': 'OPENROUTER_API_KEY',
}

OPENROUTER_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_URL = "https://api.deepseek.com"


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
    return config, default, models, commands


api_keys = read_api_keys(BASE_DIR / 'keys.txt')
CONFIG, DEFAULT_MODEL, MODELS, MODEL_COMMANDS = load_models(BASE_DIR / 'models.toml')
PREFER_OPENROUTER = CONFIG.get('prefer_openrouter', False)
SEARCH_MODEL = CONFIG.get('search_model', 'deepseek-v4-pro')
LOG_PROMPTS = CONFIG.get('log_prompts', False)

# System prompt sent to every model
try:
    with open(BASE_DIR / 'system_prompt.txt', 'r') as file:
        system_prompt = file.read().strip()
except FileNotFoundError:
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
#   (THINKING, None)  while the model is reasoning
#   (SEARCHING, None) while it searches the web (/search only)
#   (TEXT, "...")     for each piece of the answer
#   (INFO, {...})     details for the log: routing, token usage, IDs, stop reason
THINKING = 'thinking'
SEARCHING = 'searching'
TEXT = 'text'
INFO = 'info'


def details(**fields):
    """An INFO event with the fields that have a value."""
    return INFO, {k: v for k, v in fields.items() if v is not None}


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
        **({"system": system_prompt} if system_prompt else {}),
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

    usage = response.usage
    yield details(
        served_model=response.model,
        stop=response.stop_reason,
        refusal_category=getattr(response.stop_details, 'category', None) if response.stop_details else None,
        fallback=any(block.type == "fallback" for block in response.content) or None,
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        tokens_thinking=usage.output_tokens_details.thinking_tokens if usage.output_tokens_details else None,
        tokens_cache_read=usage.cache_read_input_tokens,
        tokens_cache_write=usage.cache_creation_input_tokens,
        response_id=response.id,
        request_id=getattr(response, '_request_id', None),
    )
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
        elif event.type in ("response.completed", "response.incomplete"):
            yield responses_details(event.response)
        elif event.type == "response.failed":
            yield responses_details(event.response)
            raise RuntimeError(event.response.error.message if event.response.error else "response failed")


def responses_details(response, **extra):
    """Log details from a Responses API response (OpenAI, DeepSeek search)."""
    usage = response.usage
    incomplete = response.incomplete_details
    return details(
        served_model=response.model,
        stop=response.status + (f" ({incomplete.reason})" if incomplete else ""),
        tokens_in=usage.input_tokens if usage else None,
        tokens_out=usage.output_tokens if usage else None,
        tokens_thinking=usage.output_tokens_details.reasoning_tokens if usage and usage.output_tokens_details else None,
        tokens_cache_read=usage.input_tokens_details.cached_tokens if usage and usage.input_tokens_details else None,
        response_id=response.id,
        **extra,
    )


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

    stream = client.chat.completions.create(
        model=model_id, messages=messages, stream=True,
        stream_options={"include_usage": True},  # Final chunk carries token usage
        **kwargs,
    )
    finish_reason = None
    for chunk in stream:
        if chunk.choices:
            finish_reason = chunk.choices[0].finish_reason or finish_reason
        if chunk.usage:
            usage = chunk.usage
            completion_details = usage.completion_tokens_details
            prompt_details = usage.prompt_tokens_details
            yield details(
                served_model=chunk.model,
                upstream_provider=getattr(chunk, 'provider', None),  # OpenRouter: who served it
                stop=finish_reason,
                tokens_in=usage.prompt_tokens,
                tokens_out=usage.completion_tokens,
                tokens_thinking=completion_details.reasoning_tokens if completion_details else None,
                tokens_cache_read=(prompt_details.cached_tokens if prompt_details else None)
                or getattr(usage, 'prompt_cache_hit_tokens', None),  # DeepSeek's name for it
                cost_usd=getattr(usage, 'cost', None),  # OpenRouter reports the charge
                response_id=chunk.id,
            )
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
    client = OpenAI(api_key=get_key('deepseek'), base_url=DEEPSEEK_URL)
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
    last = None
    for chunk in stream:
        last = chunk
        if not chunk.candidates or not chunk.candidates[0].content:
            continue
        for part in chunk.candidates[0].content.parts or []:
            if part.thought:
                yield THINKING, None
            elif part.text:
                yield TEXT, part.text

    if last:
        usage = last.usage_metadata
        finish = last.candidates[0].finish_reason if last.candidates else None
        yield details(
            served_model=last.model_version,
            stop=finish.name if finish else None,
            tokens_in=usage.prompt_token_count if usage else None,
            tokens_out=usage.candidates_token_count if usage else None,
            tokens_thinking=usage.thoughts_token_count if usage else None,
            tokens_cache_read=usage.cached_content_token_count if usage else None,
            response_id=last.response_id,
        )


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
    result = response.json()
    yield TEXT, result['message']['content']
    yield details(
        stop=result.get('done_reason'),
        tokens_in=result.get('prompt_eval_count'),
        tokens_out=result.get('eval_count'),
    )


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
        yield details(error=str(e))
        yield TEXT, f"Error: {e}"
        return

    native = MODELS.get(model, {}).get('provider')
    yield details(provider=provider, model_id=model_id,
                  route='openrouter fallback' if native and native != provider else 'direct')

    if provider not in PROVIDERS:
        yield details(error=f"unknown provider {provider}")
        yield TEXT, f"Error: Unknown provider '{provider}' in models.toml"
        return

    try:
        yield from PROVIDERS[provider](model_id, text, image_base64)
    except Exception as e:
        log.warning('API error from %s (%s): %s', provider, model_id, e, exc_info=True)
        yield details(error=f"{type(e).__name__}: {e}")
        yield TEXT, f"Error in {model} ({provider}: {model_id}) API call: {e}"


# /search: DeepSeek's built-in web search (Responses API). DeepSeek runs the
# searches on its servers and the model answers from the results.
def search_stream(text):
    yield details(provider='deepseek', model_id=SEARCH_MODEL, route='direct')
    try:
        client = OpenAI(api_key=get_key('deepseek'), base_url=DEEPSEEK_URL)
        stream = client.responses.create(
            model=SEARCH_MODEL,
            tools=[{"type": "web_search"}],
            # The model doesn't know today's date, and searches for the wrong year without it
            instructions=f"Today's date is {datetime.date.today():%B %d, %Y}. "
                         f"Search the web to answer with current information.\n\n{system_prompt}".strip(),
            input=text,
            stream=True,
        )
        answered = False
        for event in stream:
            if event.type == "response.output_item.added":
                if event.item.type == "reasoning":
                    yield THINKING, None
                elif event.item.type == "web_search_call":
                    yield SEARCHING, None
            elif event.type == "response.output_text.delta":
                answered = True
                yield TEXT, event.delta
            elif event.type in ("response.completed", "response.incomplete", "response.failed"):
                searches = [item for item in event.response.output if item.type == "web_search_call"]
                queries = [q for item in searches for q in (getattr(item.action, 'queries', None) or [])
                           if not q.startswith('ws_call_id=')]
                yield responses_details(
                    event.response,
                    searches=len(searches),
                    search_queries=queries if LOG_PROMPTS else None,
                )
                if event.type == "response.failed":
                    raise RuntimeError(event.response.error.message if event.response.error else "response failed")
        if not answered:
            yield details(error='search finished without an answer')
            yield TEXT, "The search finished without an answer. Try rephrasing the question."
    except Exception as e:
        log.warning('Search error (%s): %s', SEARCH_MODEL, e, exc_info=True)
        yield details(error=f"{type(e).__name__}: {e}")
        yield TEXT, f"Error in /search ({SEARCH_MODEL}): {e}"


def api_call(model, text, image_base64=None):
    return ''.join(value for kind, value in api_stream(model, text, image_base64) if kind == TEXT)
