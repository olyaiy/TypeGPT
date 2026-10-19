import base64
import datetime
import json
import logging
import tomllib
from pathlib import Path

import requests
from anthropic import Anthropic
from google import genai
from google.genai import types
from openai import OpenAI

from file_tools import TOOLS as FILE_TOOLS, FileLibrary, tools_instructions

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


def merge_config(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_config(base[key], value)
        else:
            base[key] = value


def load_models(file_path):
    with open(file_path, 'rb') as file:
        config = tomllib.load(file)
    # Personal settings (your folders, default model, ...) go in models.local.toml,
    # which git ignores; anything set there overrides models.toml
    local_path = file_path.with_name('models.local.toml')
    if local_path.exists():
        with open(local_path, 'rb') as file:
            merge_config(config, tomllib.load(file))
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
FILES_CONFIG = CONFIG.get('files', {})
OCR_MODEL = FILES_CONFIG.get('ocr_model', 'deepseek')  # A models.toml name; False turns OCR off
FILE_LIBRARY = FileLibrary(FILES_CONFIG.get('folders', []), ocr_cache_dir=BASE_DIR / '.ocr_cache',
                           ocr_model=OCR_MODEL or '')  # OCR function is attached below
FILES_ALWAYS = FILES_CONFIG.get('always', False) and bool(FILE_LIBRARY)
MAX_TOOL_ROUNDS = FILES_CONFIG.get('max_tool_rounds', 12)

# System prompt sent to every model: system_prompt.txt, plus your own
# system_prompt.local.txt (not committed) if it exists
system_prompt = ''
for name in ('system_prompt.txt', 'system_prompt.local.txt'):
    try:
        with open(BASE_DIR / name, 'r') as file:
            system_prompt = f"{system_prompt}\n\n{file.read().strip()}".strip()
    except FileNotFoundError:
        pass


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
#   (READING, None)   while it uses the file tools (/files)
#   (TEXT, "...")     for each piece of the answer
#   (INFO, {...})     details for the log: routing, token usage, IDs, stop reason
THINKING = 'thinking'
SEARCHING = 'searching'
READING = 'reading'
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


# /files: the model can list, search and read files in the folders from
# models.toml. Runs a tool-calling loop over the Chat Completions API, so it
# works with DeepSeek and every OpenRouter model.
def files_stream(model, text, image_base64=None):
    if not FILE_LIBRARY:
        yield details(error='no folders configured')
        yield TEXT, "No folders are set up for file access. Add them under [files] in models.toml."
        return
    try:
        provider, model_id = chat_completions_route(model)
        entry = MODELS.get(model, {})
    except ValueError as e:
        yield details(error=str(e))
        yield TEXT, f"Error: {e}"
        return

    yield details(provider=provider, model_id=model_id, route='direct' if provider == entry.get('provider') else
                  ('openrouter' if not entry else 'openrouter fallback'))
    try:
        yield from run_file_tools(provider, model_id, text, image_base64)
    except Exception as e:
        log.warning('Files error from %s (%s): %s', provider, model_id, e, exc_info=True)
        yield details(error=f"{type(e).__name__}: {e}")
        yield TEXT, f"Error in {model} ({provider}: {model_id}) file request: {e}"


def merge_reasoning_details(merged, new_items):
    """Joins OpenRouter's streamed reasoning_details pieces back into whole items."""
    for item in new_items or []:
        item = dict(item) if not isinstance(item, dict) else item
        key = (item.get('type'), item.get('index', 0))
        current = merged.setdefault(key, {})
        for field, value in item.items():
            if field in ('text', 'summary', 'data') and isinstance(value, str):
                current[field] = current.get(field, '') + value
            elif value is not None:
                current[field] = value


def chat_completions_route(model):
    """(provider, model_id) for features that need the Chat Completions API (tools, OCR).

    DeepSeek and OpenRouter models are used as they are; Anthropic, OpenAI and
    Gemini models go through their OpenRouter ID.
    """
    provider, model_id = resolve_model(model)
    if provider in ('deepseek', 'openrouter'):
        return provider, model_id
    entry = MODELS.get(model, {})
    if entry.get('openrouter') and has_key('openrouter'):
        return 'openrouter', entry['openrouter']
    raise ValueError(f"This needs a DeepSeek model or OPENROUTER_API_KEY (selected: {model})")


def chat_client(provider):
    """An OpenAI-compatible client and extra request options for DeepSeek or OpenRouter."""
    if provider == 'deepseek':
        return OpenAI(api_key=get_key('deepseek'), base_url=DEEPSEEK_URL), {}
    client = OpenAI(api_key=get_key('openrouter'), base_url=OPENROUTER_URL)
    return client, {"extra_headers": {"HTTP-Referer": "https://github.com/olyaiy/TypeGPT",
                                      "X-OpenRouter-Title": "TypeGPT"}}


OCR_PROMPT = (
    "Transcribe all the text on this page exactly, including text inside images. "
    "Then describe each picture, chart or diagram in one or two sentences: what it shows and "
    "any labels or numbers in it. Skip decorative shapes and backgrounds. Plain text only."
)


def ocr_image(jpeg_bytes):
    """Reads a page image with the OCR model (DeepSeek Flash by default). Used by file_tools."""
    provider, model_id = chat_completions_route(OCR_MODEL)
    client, extra = chat_client(provider)
    if provider == 'deepseek':
        extra['extra_body'] = {"thinking": {"type": "disabled"}}  # Faster and cheaper; not needed to transcribe
    response = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": OCR_PROMPT},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode()}},
        ]}],
        **extra,
    )
    return (response.choices[0].message.content or '').strip()


if OCR_MODEL:
    FILE_LIBRARY.ocr = ocr_image


def run_file_tools(provider, model_id, text, image_base64):
    client, extra = chat_client(provider)

    content = [{"type": "text", "text": text}]
    if image_base64:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
    instructions = f"{system_prompt}\n\n{tools_instructions(FILE_LIBRARY)}".strip()
    messages = [{"role": "system", "content": instructions}, {"role": "user", "content": content}]

    totals = {'tokens_in': 0, 'tokens_out': 0, 'tokens_thinking': 0, 'tokens_cache_read': 0, 'cost_usd': 0.0}
    tool_counts, files_read, queries, tool_rounds = {}, [], [], 0
    answered, finish_reason, served_model, response_id, upstream = False, None, None, None, None

    for round_number in range(1, MAX_TOOL_ROUNDS + 2):
        last_round = round_number > MAX_TOOL_ROUNDS  # Out of tool rounds: must answer now
        stream = client.chat.completions.create(
            model=model_id, messages=messages, tools=FILE_TOOLS,
            tool_choice="none" if last_round else "auto",
            stream=True, stream_options={"include_usage": True}, **extra,
        )
        text_parts, reasoning_parts, reasoning_details, calls = [], [], {}, {}
        for chunk in stream:
            served_model, response_id = chunk.model or served_model, chunk.id or response_id
            upstream = getattr(chunk, 'provider', None) or upstream
            if chunk.usage:
                usage = chunk.usage
                totals['tokens_in'] += usage.prompt_tokens or 0
                totals['tokens_out'] += usage.completion_tokens or 0
                if usage.completion_tokens_details:
                    totals['tokens_thinking'] += usage.completion_tokens_details.reasoning_tokens or 0
                cached = (usage.prompt_tokens_details.cached_tokens if usage.prompt_tokens_details else None) \
                    or getattr(usage, 'prompt_cache_hit_tokens', None)
                totals['tokens_cache_read'] += cached or 0
                totals['cost_usd'] += getattr(usage, 'cost', None) or 0
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason or finish_reason
            delta = choice.delta
            reasoning = getattr(delta, 'reasoning_content', None) or getattr(delta, 'reasoning', None)
            details_items = getattr(delta, 'reasoning_details', None)
            if reasoning or details_items:
                yield THINKING, None
                if getattr(delta, 'reasoning_content', None):
                    reasoning_parts.append(delta.reasoning_content)
                merge_reasoning_details(reasoning_details, details_items)
            if delta.content:
                answered = True
                text_parts.append(delta.content)
                yield TEXT, delta.content
            for call in delta.tool_calls or []:
                current = calls.setdefault(call.index, {'id': None, 'name': '', 'arguments': ''})
                current['id'] = call.id or current['id']
                if call.function and call.function.name:
                    current['name'] += call.function.name
                if call.function and call.function.arguments:
                    current['arguments'] += call.function.arguments

        if not calls:
            break

        # Send the model's turn back unchanged; DeepSeek returns 400 without reasoning_content
        assistant = {
            "role": "assistant",
            "content": ''.join(text_parts) or None,
            "tool_calls": [{"id": c['id'], "type": "function",
                            "function": {"name": c['name'], "arguments": c['arguments'] or '{}'}}
                           for c in calls.values()],
        }
        if reasoning_parts:
            assistant["reasoning_content"] = ''.join(reasoning_parts)
        if reasoning_details:
            assistant["reasoning_details"] = list(reasoning_details.values())
        messages.append(assistant)

        yield READING, None
        tool_rounds += 1
        for c in calls.values():
            result = FILE_LIBRARY.call(c['name'], c['arguments'])
            tool_counts[c['name']] = tool_counts.get(c['name'], 0) + 1
            try:
                args = json.loads(c['arguments'] or '{}')
            except json.JSONDecodeError:
                args = {}
            if c['name'] == 'read_file' and args.get('path'):
                files_read.append(args['path'] + (f" p{args['start_page']}" if args.get('start_page', 1) != 1 else ''))
            if c['name'] == 'search_files' and args.get('query'):
                queries.append(args['query'])
            log.info('files | tool %s %s -> %d chars%s', c['name'],
                     json.dumps(args) if LOG_PROMPTS or c['name'] != 'search_files' else '(query hidden)',
                     len(result), ' (error)' if result.startswith('Error') else '')
            messages.append({"role": "tool", "tool_call_id": c['id'], "content": result})

    yield details(
        served_model=served_model,
        upstream_provider=upstream,
        stop=finish_reason,
        tool_rounds=tool_rounds or None,
        tool_calls=' '.join(f'{name}:{count}' for name, count in tool_counts.items()) or None,
        files_read=files_read or None,
        search_queries=queries if LOG_PROMPTS and queries else None,
        response_id=response_id,
        **{k: v for k, v in totals.items() if v},
    )
    if not answered:
        yield details(error='finished without an answer')
        yield TEXT, "No answer came back. Try asking again or more specifically."


def api_call(model, text, image_base64=None):
    return ''.join(value for kind, value in api_stream(model, text, image_base64) if kind == TEXT)
