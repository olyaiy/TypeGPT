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
}


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
    return config.get('default', next(iter(models))), models, commands


api_keys = read_api_keys(BASE_DIR / 'keys.txt')
DEFAULT_MODEL, MODELS, MODEL_COMMANDS = load_models(BASE_DIR / 'models.toml')

# System prompt text
with open(BASE_DIR / 'system_prompt.txt', 'r') as file:
    # system_prompt = file.read()
    system_prompt = ''


def get_key(provider):
    key = api_keys.get(KEY_NAMES[provider], '')
    if not key or key.startswith('your'):
        raise ValueError(f"{KEY_NAMES[provider]} is missing from keys.txt")
    return key


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

    response = client.beta.messages.create(
        model=model_id,
        max_tokens=16000,
        system=system_prompt,
        messages=[{"role": "user", "content": content}],
        # If a safety classifier declines, retry on a fallback model in the same call
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )

    if response.stop_reason == "refusal":
        return "Claude declined to answer this request."
    return ''.join(block.text for block in response.content if block.type == "text")


# Function to query OpenAI (Responses API)
def query_openai(model_id, text, image_base64=None):
    client = OpenAI(api_key=get_key('openai'))

    content = [{"type": "input_text", "text": text}]
    if image_base64:
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{image_base64}"
        })

    response = client.responses.create(
        model=model_id,
        instructions=system_prompt or None,
        input=[{"role": "user", "content": content}],
    )
    return response.output_text


# Function to query DeepSeek (OpenAI-compatible Chat Completions API)
def query_deepseek(model_id, text, image_base64=None):
    client = OpenAI(api_key=get_key('deepseek'), base_url="https://api.deepseek.com")

    content = [{"type": "text", "text": text}]
    if image_base64:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    messages = [{"role": "user", "content": content}]
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})

    response = client.chat.completions.create(model=model_id, messages=messages)
    return response.choices[0].message.content


# Function to query Gemini
def query_gemini(model_id, text, image_base64=None):
    client = genai.Client(api_key=get_key('gemini'))

    contents = [text]
    if image_base64:
        contents.append(types.Part.from_bytes(
            data=base64.b64decode(image_base64),
            mime_type="image/png"
        ))

    response = client.models.generate_content(
        model=model_id,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_prompt or None),
    )
    return response.text


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
    return response.json()['message']['content']


PROVIDERS = {
    'anthropic': query_anthropic,
    'openai': query_openai,
    'deepseek': query_deepseek,
    'gemini': query_gemini,
    'ollama': query_ollama,
}


# main function
def api_call(model, text, image_base64=None):
    if model not in MODELS:
        return f"Error: Unsupported model '{model}'"

    entry = MODELS[model]
    provider = entry['provider']
    if provider not in PROVIDERS:
        return f"Error: Unknown provider '{provider}' in models.toml"

    try:
        return PROVIDERS[provider](entry['model'], text, image_base64)
    except Exception as e:
        return f"Error in {model} ({entry['model']}) API call: {e}"
