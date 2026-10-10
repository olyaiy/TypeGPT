"""Model providers. Each one takes (prompt, image_png_b64, settings) and returns the reply text.

Every provider raises on failure; the caller decides how to report the error.
"""
import requests

import config


def _post(url, settings, **kwargs):
    response = requests.post(url, timeout=float(settings['TYPEGPT_TIMEOUT']), **kwargs)
    if not response.ok:
        raise RuntimeError(f'{response.status_code} from {url}: {response.text[:500]}')
    return response.json()


def query_openai(prompt, image_b64, settings):
    content = [{'type': 'input_text', 'text': prompt}]
    if image_b64:
        content.append({'type': 'input_image', 'image_url': f'data:image/png;base64,{image_b64}'})
    body = {'model': settings['OPENAI_MODEL'], 'input': [{'role': 'user', 'content': content}]}
    if system := config.system_prompt():
        body['instructions'] = system
    data = _post(
        'https://api.openai.com/v1/responses', settings, json=body,
        headers={'Authorization': f"Bearer {config.get(settings, 'OPENAI_API_KEY')}"},
    )
    return ''.join(
        part.get('text', '')
        for item in data.get('output', []) if item.get('type') == 'message'
        for part in item.get('content', []) if part.get('type') == 'output_text'
    )


def query_claude(prompt, image_b64, settings):
    content = [{'type': 'text', 'text': prompt}]
    if image_b64:
        content.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image_b64}})
    body = {
        'model': settings['ANTHROPIC_MODEL'],
        'max_tokens': int(settings['TYPEGPT_MAX_TOKENS']),
        'messages': [{'role': 'user', 'content': content}],
    }
    if system := config.system_prompt():
        body['system'] = system
    data = _post(
        'https://api.anthropic.com/v1/messages', settings, json=body,
        headers={'x-api-key': config.get(settings, 'ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'},
    )
    return ''.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text')


def query_gemini(prompt, image_b64, settings):
    parts = [{'text': prompt}]
    if image_b64:
        parts.append({'inline_data': {'mime_type': 'image/png', 'data': image_b64}})
    body = {'contents': [{'role': 'user', 'parts': parts}]}
    if system := config.system_prompt():
        body['system_instruction'] = {'parts': [{'text': system}]}
    model = settings['GEMINI_MODEL']
    data = _post(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent', settings, json=body,
        headers={'x-goog-api-key': config.get(settings, 'GEMINI_API_KEY')},
    )
    candidates = data.get('candidates') or [{}]
    return ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', []))


def query_ollama(prompt, image_b64, settings):
    messages = []
    if system := config.system_prompt():
        messages.append({'role': 'system', 'content': system})
    user = {'role': 'user', 'content': prompt}
    if image_b64:
        user['images'] = [image_b64]
    messages.append(user)
    data = _post(
        f"{settings['OLLAMA_URL'].rstrip('/')}/api/chat", settings,
        json={'model': settings['OLLAMA_MODEL'], 'messages': messages, 'stream': False},
    )
    return data['message']['content']


PROVIDERS = {
    'claude': query_claude,
    'chatgpt': query_openai,
    'gemini': query_gemini,
    'llama3': query_ollama,
}

# Extra names accepted as /commands
ALIASES = {'gpt': 'chatgpt', 'openai': 'chatgpt', 'llama': 'llama3', 'ollama': 'llama3'}


def api_call(provider, prompt, image_b64, settings):
    reply = PROVIDERS[provider](prompt, image_b64, settings)
    if not reply.strip():
        raise RuntimeError(f'{provider} returned an empty reply')
    return reply
