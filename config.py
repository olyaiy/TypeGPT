"""Configuration: API keys, model IDs and settings.

Values come from environment variables first, then from `keys.txt` (or `.env`)
next to this file. Missing keys only cause an error when that provider is used.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KEY_FILES = [ROOT / 'keys.txt', ROOT / '.env']
SYSTEM_PROMPT_FILE = ROOT / 'system_prompt.txt'

DEFAULTS = {
    # Models
    'OPENAI_MODEL': 'gpt-6.1-sol',
    'ANTHROPIC_MODEL': 'claude-opus-5-5',
    'GEMINI_MODEL': 'gemini-3.8-flash',
    'OLLAMA_MODEL': 'llama3',
    'OLLAMA_URL': 'http://localhost:11434',
    # Behaviour
    'TYPEGPT_DEFAULT_PROVIDER': 'claude',   # claude | chatgpt | gemini | llama3
    'TYPEGPT_HOTKEY': '<cmd>+<shift>+<space>',  # pynput hotkey syntax
    'TYPEGPT_OUTPUT_MODE': 'append',        # append (keep your prompt) | replace
    'TYPEGPT_TIMEOUT': '120',               # seconds per API request
    'TYPEGPT_MAX_TOKENS': '4096',
}


def _read_key_file(path):
    """Parse KEY=VALUE lines. Tolerates blank lines, comments, quotes and '=' in values."""
    values = {}
    try:
        text = path.read_text()
    except (FileNotFoundError, PermissionError):
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip().removeprefix('export ').strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


def load():
    """Return the merged settings dict (env vars override files, files override defaults)."""
    settings = dict(DEFAULTS)
    for path in KEY_FILES:
        settings.update({k: v for k, v in _read_key_file(path).items() if v})
    settings.update({k: v for k, v in os.environ.items() if k in settings or k.endswith('_API_KEY')})
    return settings


def get(settings, name):
    """Fetch a required setting, with a readable error if it's missing or still a placeholder."""
    value = settings.get(name, '')
    if not value or value.startswith('your'):
        raise RuntimeError(f'{name} is not set. Add it to keys.txt or your environment.')
    return value


def system_prompt():
    try:
        return SYSTEM_PROMPT_FILE.read_text().strip()
    except FileNotFoundError:
        return ''
