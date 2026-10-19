"""Detailed per-request logging for typegpt.log.

Each request gets two lines: one when it's sent, and one when it finishes
with timings, routing, token usage, IDs and the outcome. Prompt and answer
text are logged only when log_prompts = true in models.toml.
"""
import itertools
import json
import logging
import time

log = logging.getLogger('typegpt')
_request_numbers = itertools.count(1)

# Order of fields in the "done" line; anything else reported is appended after
FIELD_ORDER = [
    'status', 'total', 'first_output', 'first_text', 'thinking', 'thinking_spans',
    'searching', 'searches', 'answering', 'typing', 'answer_chars', 'answer_lines',
    'provider', 'model_id', 'route', 'served_model', 'upstream_provider', 'fallback',
    'stop', 'refusal_category', 'tokens_in', 'tokens_cache_read', 'tokens_cache_write',
    'tokens_out', 'tokens_thinking', 'cost_usd', 'response_id', 'request_id',
    'error', 'timeline',
]


def format_value(value, key=''):
    if key == 'cost_usd':
        return f'{value:.6f}'
    if isinstance(value, float):
        return f'{value:.2f}'
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    value = str(value)
    return json.dumps(value) if (' ' in value or not value) else value


def format_fields(fields):
    keys = [k for k in FIELD_ORDER if k in fields] + [k for k in fields if k not in FIELD_ORDER]
    return ' '.join(f'{k}={format_value(fields[k], k)}' for k in keys)


def describe_image(image_base64, source):
    if not image_base64:
        return None
    size_kb = len(image_base64) * 3 / 4 / 1024
    return f'{source} ({size_kb:.0f} KB)'


class RequestTrace:
    """Times one request from send to the last typed character."""

    def __init__(self, command, model, prompt, image=None, log_prompts=False):
        self.number = next(_request_numbers)
        self.log_prompts = log_prompts
        self.started = time.monotonic()
        self.info = {}
        self.timeline = []
        self.durations = {}
        self.thinking_spans = 0
        self.searches = 0
        self.state = None
        self.state_since = None
        self.first_output = None
        self.first_text = None
        self.answer_chars = 0
        self.answer_lines = 0
        self.typing = 0.0
        self.answer_parts = []

        fields = {'command': command, 'model': model, 'prompt_chars': len(prompt)}
        if image:
            fields['image'] = image
        log.info('request #%d sent | %s', self.number, format_fields(fields))
        if log_prompts:
            log.info('request #%d prompt: %s', self.number, json.dumps(prompt))

    def elapsed(self):
        return time.monotonic() - self.started

    def _switch(self, state):
        if state == self.state:
            return
        now = time.monotonic()
        if self.state:
            self.durations[self.state] = self.durations.get(self.state, 0) + now - self.state_since
        self.state, self.state_since = state, now
        if state:
            self.timeline.append(f'{state}@{now - self.started:.1f}s')

    def event(self, kind, value):
        """Record one (kind, value) event from api_stream / search_stream."""
        if kind == 'info':
            self.info.update(value)
            return
        if self.first_output is None:
            self.first_output = self.elapsed()
        if kind == 'thinking':
            if self.state != 'thinking':
                self.thinking_spans += 1
            self._switch('thinking')
        elif kind == 'searching':
            self.searches += 1  # One event per web search
            self._switch('searching')
        elif kind == 'text':
            if self.first_text is None:
                self.first_text = self.elapsed()
            self._switch('answering')
            self.answer_chars += len(value)
            self.answer_lines += value.count('\n')
            if self.log_prompts:
                self.answer_parts.append(value)

    def add_typing(self, seconds):
        self.typing += seconds

    def finish(self, exception=None):
        self._switch(None)
        fields = {
            'total': self.elapsed(),
            'first_output': self.first_output,
            'first_text': self.first_text,
            'thinking': self.durations.get('thinking'),
            'thinking_spans': self.thinking_spans or None,
            'searching': self.durations.get('searching'),
            'searches': self.searches or None,
            'answering': self.durations.get('answering'),
            'typing': self.typing or None,
            'answer_chars': self.answer_chars,
            'answer_lines': self.answer_lines + 1 if self.answer_chars else 0,
        }
        fields.update(self.info)  # Provider details (a search's own count wins)
        if exception is not None:
            fields['error'] = f'{type(exception).__name__}: {exception}'

        if 'error' in fields:
            fields['status'] = 'error'
        elif not self.answer_chars:
            fields['status'] = 'empty'
        else:
            fields['status'] = 'ok'
        fields['timeline'] = ' '.join(self.timeline)
        fields = {k: v for k, v in fields.items() if v is not None}

        level = logging.WARNING if fields['status'] != 'ok' else logging.INFO
        log.log(level, 'request #%d done | %s', self.number, format_fields(fields))
        if self.log_prompts:
            log.info('request #%d answer: %s', self.number, json.dumps(''.join(self.answer_parts)))
