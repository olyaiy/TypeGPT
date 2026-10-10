"""TypeGPT: select text anywhere, press the hotkey, and the AI's reply is pasted in.

Flow:
  hotkey (key listener thread)  ->  worker thread:
    copy selection -> parse /commands -> call model -> paste reply -> restore clipboard

The key listener only flips state and starts the worker, so it never blocks.
"""
import base64
import io
import platform
import subprocess
import sys
import threading
import time
import uuid

import pyperclip
from PIL import Image, ImageGrab
from pynput import keyboard

import config
from api_calls import ALIASES, PROVIDERS, api_call

IS_MAC = platform.system() == 'Darwin'
MOD = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl  # copy/paste modifier
MODIFIERS = {
    keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r,
    keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r,
    keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
    keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r,
}
MAX_IMAGE_SIDE = 1568  # keeps images inside every provider's size limits
FLAGS = {'see', 'clip'}


def parse_prompt(text, current_provider):
    """Strip leading /commands from the selection.

    Returns (provider, prompt, flags, switch_default). `switch_default` is True when the
    selection was only a model command (e.g. "/gemini"), which changes the default model.
    """
    provider, flags = current_provider, set()
    words = text.strip().split(maxsplit=1)
    while words and words[0].startswith('/'):
        name = words[0][1:].lower()
        name = ALIASES.get(name, name)
        if name in PROVIDERS:
            provider = name
        elif name in FLAGS:
            flags.add(name)
        else:
            break  # not a command, e.g. "/usr/bin is a path"
        words = words[1].split(maxsplit=1) if len(words) > 1 else []
    prompt = ' '.join(words)
    switch_default = not prompt and not flags and provider != current_provider
    return provider, prompt, flags, switch_default


def encode_image(image):
    """Downscale and base64-encode a PIL image as PNG."""
    image = image.convert('RGB')
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    buffer = io.BytesIO()
    image.save(buffer, format='PNG', optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


def notify(message):
    print(f'[TypeGPT] {message}', flush=True)
    if IS_MAC:
        safe = message.replace('\\', '\\\\').replace('"', '\\"')[:200]
        subprocess.Popen(['osascript', '-e', f'display notification "{safe}" with title "TypeGPT"'],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class TypeGPT:
    def __init__(self):
        self.settings = config.load()
        self.provider = self.settings['TYPEGPT_DEFAULT_PROVIDER']
        if self.provider not in PROVIDERS:
            raise SystemExit(f'Unknown TYPEGPT_DEFAULT_PROVIDER: {self.provider}')
        self.output_mode = self.settings['TYPEGPT_OUTPUT_MODE']
        self.controller = keyboard.Controller()
        self.busy = threading.Lock()
        self.held = set()  # physical modifier keys currently down
        self.hotkey = keyboard.HotKey(keyboard.HotKey.parse(self.settings['TYPEGPT_HOTKEY']), self.on_hotkey)
        self.listener = None

    # ---- key listener (must stay fast; runs on the OS input thread) ----

    def on_press(self, key, injected=False):
        if injected:  # ignore our own simulated Cmd+C / Cmd+V
            return
        if key in MODIFIERS:
            self.held.add(key)
        self.hotkey.press(self.listener.canonical(key))

    def on_release(self, key, injected=False):
        if injected:
            return
        self.held.discard(key)
        self.hotkey.release(self.listener.canonical(key))

    def on_hotkey(self):
        if self.busy.locked():
            notify('Still working on the last request.')
            return
        threading.Thread(target=self.handle_request, daemon=True).start()

    # ---- worker thread ----

    def handle_request(self):
        with self.busy:
            original = pyperclip.paste()
            try:
                self._handle_request(original)
            except Exception as error:  # report, never type errors into the user's document
                notify(f'Error: {error}')
            finally:
                time.sleep(0.3)  # let the target app read the clipboard before restoring it
                pyperclip.copy(original)

    def _handle_request(self, original_text):
        self.wait_for_modifiers_released()
        # An image on the clipboard reads as empty text; only then is it worth grabbing (for /clip)
        clipboard_image = None if original_text else self.grab_clipboard_image()
        selection = self.copy_selection()
        if not selection:
            notify('Select some text first, then press the hotkey.')
            return

        provider, prompt, flags, switch_default = parse_prompt(selection, self.provider)
        if switch_default:
            self.provider = provider
            notify(f'Default model is now {provider}.')
            return
        if not prompt and not flags:
            notify('Nothing to send.')
            return

        image_b64 = None
        if 'see' in flags:
            image_b64 = encode_image(ImageGrab.grab())
        elif 'clip' in flags:
            if clipboard_image is None:
                notify('No image on the clipboard.')
                return
            image_b64 = encode_image(clipboard_image)

        notify(f'Asking {provider}...')
        started = time.monotonic()
        reply = api_call(provider, prompt or 'Describe this image.', image_b64, self.settings).strip()
        print(f'[TypeGPT] {provider} replied in {time.monotonic() - started:.1f}s', flush=True)
        self.paste_reply(reply)

    def wait_for_modifiers_released(self, timeout=2.0):
        """Wait until the hotkey's modifiers are up, so our Cmd+C isn't Cmd+Shift+C."""
        deadline = time.monotonic() + timeout
        while self.held and time.monotonic() < deadline:
            time.sleep(0.02)

    @staticmethod
    def grab_clipboard_image():
        try:
            image = ImageGrab.grabclipboard()
        except Exception:
            return None
        return image if isinstance(image, Image.Image) else None

    def press_combo(self, *keys):
        with self.controller.pressed(MOD):
            for key in keys:
                self.controller.tap(key)

    def copy_selection(self, timeout=0.8):
        """Copy the current selection via the clipboard. Returns '' if nothing is selected."""
        sentinel = f'typegpt-{uuid.uuid4()}'
        pyperclip.copy(sentinel)
        self.press_combo('c')
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = pyperclip.paste()
            if text != sentinel:
                return text
            time.sleep(0.02)
        return ''

    def paste_reply(self, reply):
        if self.output_mode == 'append':
            self.controller.tap(keyboard.Key.right)  # collapse the selection to its end
            reply = '\n\n' + reply
        pyperclip.copy(reply)
        self.press_combo('v')

    # ---- lifecycle ----

    def run(self):
        print(f"TypeGPT running. Select text and press {self.settings['TYPEGPT_HOTKEY']}.", flush=True)
        print(f'Default model: {self.provider}. Output mode: {self.output_mode}. Ctrl+C to quit.', flush=True)
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        self.listener.start()
        self.listener.wait()
        if IS_MAC and not getattr(self.listener, 'IS_TRUSTED', True):
            print('\nmacOS has not granted keyboard access yet. In System Settings > Privacy & Security,\n'
                  'enable your terminal (or Python) under Accessibility and Input Monitoring, then restart.\n',
                  flush=True)
        try:
            self.listener.join()
        except KeyboardInterrupt:
            pass
        finally:
            self.listener.stop()


if __name__ == '__main__':
    try:
        TypeGPT().run()
    except KeyboardInterrupt:
        sys.exit(0)
