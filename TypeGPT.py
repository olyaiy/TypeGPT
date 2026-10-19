import pyautogui
import base64
from io import BytesIO
from pynput import keyboard
import pyperclip
import api_calls
from api_calls import (api_stream, search_stream, files_stream, openrouter_model_exists, DEFAULT_MODEL,
                       MODELS, MODEL_COMMANDS, SEARCH_MODEL, LOG_PROMPTS, FILE_LIBRARY, FILES_ALWAYS,
                       THINKING, SEARCHING, READING, TEXT)
from request_log import RequestTrace, describe_image
import sys
from PIL import Image, ImageGrab
import io
import logging
import logging.handlers
import platform
import signal
import threading
import time
from pathlib import Path

IS_MAC = platform.system() == 'Darwin'

# Exit codes run.sh and the GUI understand
EXIT_RESTART = 42          # /restart: relaunch right away
EXIT_NO_PERMISSIONS = 3    # don't relaunch
EXIT_TOO_MANY_CRASHES = 2  # don't relaunch

LOG_FILE = Path(__file__).resolve().parent / 'typegpt.log'
log = logging.getLogger('typegpt')


def setup_logging():
    log.setLevel(logging.INFO)
    file_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=1)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [pid %(process)d] %(message)s'))
    log.addHandler(file_handler)
    log.addHandler(logging.StreamHandler())
    # Anything uncaught, on any thread, ends up in the log
    sys.excepthook = lambda *exc: log.critical('Uncaught exception', exc_info=exc)
    threading.excepthook = lambda args: log.error(
        'Uncaught exception in thread', exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


class SafeListener(keyboard.Listener):
    """A keyboard listener that skips key events it can't read instead of stopping.

    On macOS pynput only catches IndexError while reading the character for a key
    event, so an undecodable one (e.g. half of an emoji) raised UnicodeDecodeError
    and stopped the whole listener.
    """

    def _event_to_key(self, event):
        try:
            return super()._event_to_key(event)
        except IndexError:
            raise  # pynput already handles this
        except Exception:
            log.warning('Skipped a key event that could not be read', exc_info=True)
            return None


def guarded(default=None):
    """Logs any error in a listener callback instead of letting it stop the listener."""
    def decorator(f):
        def wrapper(self, *args, **kwargs):
            try:
                return f(self, *args, **kwargs)
            except Exception:
                log.exception('Error handling a key event')
                self.cancel_input()
                return default
        return wrapper
    return decorator

# Cmd on macOS, Ctrl on Windows/Linux
MODIFIER_KEYS = (
    {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r} if IS_MAC
    else {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
)
SHIFT_KEYS = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}
PASTE_CHARS = ('v', 'V', '\x16')  # '\x16' is what Ctrl+V reports on some platforms
# Shown while the model works, erased when the answer starts
STATUS_LABELS = {THINKING: '(thinking)', SEARCHING: '(searching)', READING: '(reading files)'}
SEND_KEYS = 'Cmd+Shift+Enter' if IS_MAC else 'Ctrl+Shift+Enter'
# press() types these literally, so map them to the real keys
CONTROL_KEYS = {'\n': keyboard.Key.enter, '\r': keyboard.Key.enter, '\t': keyboard.Key.tab}


class TypeGPT:
    def __init__(self):
        self.listening = False
        self.captured_text = ''
        self.keyboard_controller = keyboard.Controller()
        self.mode = None
        self.model = DEFAULT_MODEL
        self.special_keys = {
            'modifier': False,
            'shift': False,
        }
        self.screenshot = None
        self.screenshot_base64 = None
        self.should_quit = False
        self.should_restart = False
        self.busy = False
        self.started_at = time.monotonic()
        self.request_count = 0
        self.screenshot_source = None
        self.commands = {
            '/quit': self.quit,
            '/stop': self.stop_listening,
            '/a': lambda: self.set_mode('line'),
            '/see': self.capture_screenshot,
            '/search': lambda: self.set_mode('search'),
            '/files': lambda: self.set_mode('files'),
            '/model': lambda: self.set_mode('model'),
            '/check': self.check_model,
            '/restart': self.restart,
            '/help': self.show_help,
        }
        for command, model in MODEL_COMMANDS.items():
            self.commands[f'/{command}'] = lambda model=model: self.select_model(model)
        # A command fires as soon as it's typed, so one that starts with another can't be reached
        for command in self.commands:
            shorter = [c for c in self.commands if c != command and command.startswith(c)]
            if shorter:
                log.warning('command %s can never run: %s fires first. Rename it in models.toml', command, shorter[0])

    @guarded()
    def on_press(self, key, injected=False):
        # Ignore the keystrokes TypeGPT types itself
        if injected:
            return
        self.handle_special_keys(key, pressed=True)

        if key == keyboard.Key.backspace:
            self.handle_backspace()
        elif key == keyboard.Key.space:
            self.process_character(' ')
        elif isinstance(key, keyboard.KeyCode) and key.char is not None:
            self.process_character(key.char)

    @guarded(default=True)
    def on_release(self, key, injected=False):
        if injected:
            return True
        self.handle_special_keys(key, pressed=False)

        if key == keyboard.Key.esc and self.listening:
            log.info('input cancelled with Esc | mode=%s chars_discarded=%d', self.mode, len(self.captured_text))
            self.cancel_input()

        if (key == keyboard.Key.enter and
            self.special_keys['modifier'] and
            self.special_keys['shift']):
            self.process_enter_key()

        if self.should_restart or self.should_quit:
            return False  # This will stop the listener

        return True  # Keep the listener running otherwise

    def handle_special_keys(self, key, pressed):
        if key in MODIFIER_KEYS:
            self.special_keys['modifier'] = pressed
        elif key in SHIFT_KEYS:
            self.special_keys['shift'] = pressed

    def process_character(self, char):
        if self.special_keys['modifier']:
            # Shortcuts like Cmd+C aren't typed text; only paste is captured
            if self.listening and char in PASTE_CHARS:
                self.handle_paste()
            return

        if not self.listening:
            if char == '/':
                self.start_listening()
        elif self.mode is None:
            # Typing a command
            if char == '/':
                self.start_listening()
            else:
                self.captured_text += char
                self.process_commands()
        else:
            # Typing a prompt; '/' is allowed here
            self.captured_text += char

    def start_listening(self):
        self.listening = True
        self.mode = None
        self.captured_text = '/'

    def handle_backspace(self):
        if not self.listening:
            return
        self.captured_text = self.captured_text[:-1]
        if self.mode is None and not self.captured_text:
            self.listening = False

    def handle_paste(self):
        image = ImageGrab.grabclipboard()
        if isinstance(image, Image.Image):
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            self.captured_text += f"[IMAGE:{img_str}]"
            log.info('paste | image %dx%d (%d KB)', image.width, image.height, len(buffered.getvalue()) // 1024)
            self.type_output("(image pasted)")
        else:
            text = pyperclip.paste()
            self.captured_text += text
            log.info('paste | text %d chars', len(text))

    def process_commands(self):
        func = self.commands.get(self.captured_text)
        if func:
            self.captured_text = ''  # Clear the captured text before running the command
            func()
        elif not any(cmd.startswith(self.captured_text) for cmd in self.commands):
            # Not a command (e.g. a URL or a fraction), stop watching
            self.listening = False
            self.captured_text = ''

    def capture_screenshot(self):
        started = time.monotonic()
        try:
            self.screenshot = pyautogui.screenshot()
        except Exception:
            # Usually missing Screen Recording permission on macOS
            log.warning('command /see: screenshot failed (Screen Recording permission?)', exc_info=True)
            self.cancel_input()
            self.type_output(" ...screenshot failed. Allow Screen Recording for this app in System Settings.")
            return
        buffered = BytesIO()
        self.screenshot.save(buffered, format="PNG")
        self.screenshot_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        log.info('command /see | screenshot %dx%d (%d KB) in %.2fs', self.screenshot.width, self.screenshot.height,
                 len(buffered.getvalue()) // 1024, time.monotonic() - started)
        self.type_output(" ss captured: ")
        self.mode = 'screenshot'

    def quit(self):
        log.info('command /quit')
        self.type_output(' ...quitting.')
        self.should_quit = True  # Set the flag to quit

    def stop_listening(self):
        log.info('command /stop')
        self.cancel_input()
        self.type_output(' ...stopped.')

    def cancel_input(self):
        self.listening = False
        self.captured_text = ''
        self.mode = None
        self.screenshot = None
        self.screenshot_base64 = None

    def set_mode(self, mode):
        log.info('input started | mode=%s model=%s', mode, self.model)
        self.mode = mode
        if mode == 'line':
            self.type_output(": ")
        elif mode == 'model':
            self.type_output(" model: ")
        elif mode == 'search':
            self.type_output(" search: ")
        elif mode == 'files':
            self.type_output(" files: ")

    def select_model(self, model):
        log.info('model switched | %s -> %s (%s)', self.model, model, MODELS.get(model, {}).get('model', model))
        self.model = model
        self.listening = False
        self.type_output(f' ... {model.capitalize()} selected.')

    def choose_model(self, name):
        self.listening = False
        self.mode = None
        if name in MODEL_COMMANDS:
            self.select_model(MODEL_COMMANDS[name])
        elif openrouter_model_exists(name):
            log.info('model switched | %s -> %s (OpenRouter, via /model)', self.model, name)
            self.model = name
            self.type_output(f' ... {name} selected (OpenRouter).')
        else:
            log.info('command /model: unknown model %r', name)
            self.type_output(f' ... unknown model: {name}')

    def show_help(self):
        log.info('command /help')
        self.listening = False
        self.mode = None
        lines = [
            '',
            'TypeGPT commands:',
            f'/a  ask a question, then {SEND_KEYS} to send',
            f'/see  ask about a screenshot, then {SEND_KEYS} to send',
            f'/search  ask with web search ({SEARCH_MODEL}), then {SEND_KEYS} to send',
            f'/files  ask about your files ({", ".join(FILE_LIBRARY.roots) or "none set up"}), then {SEND_KEYS}',
            f'/model  type any OpenRouter model ID, then {SEND_KEYS}',
            '/check  show the active model',
            '/stop  cancel input (or press Esc)',
            '/restart  restart TypeGPT',
            '/quit  quit TypeGPT',
            '/help  show this list',
            f'File access on every question: {"on" if FILES_ALWAYS else "off"}',
            'Models:',
        ]
        for name, entry in MODELS.items():
            commands = ', '.join(f'/{c}' for c in [name, *entry.get('aliases', [])])
            active = '  (active)' if name == self.model else ''
            lines.append(f'{commands}  {entry["model"]}{active}')
        threading.Thread(target=self.type_output, args=('\n'.join(lines),), daemon=True).start()

    def check_model(self):
        log.info('command /check | model=%s', self.model)
        self.type_output(f" -> {self.model} selected.")
        self.listening = False
        self.mode = None

    def process_enter_key(self):
        if self.listening and self.mode == 'model':
            self.choose_model(self.captured_text.strip())
        elif self.listening and self.mode in ['line', 'screenshot', 'search', 'files']:
            if self.busy:
                log.info('send ignored | still answering the previous request')
                return
            text, screenshot_base64 = self.captured_text, self.screenshot_base64
            command = {'line': '/a', 'screenshot': '/see', 'search': '/search', 'files': '/files'}[self.mode]
            self.cancel_input()
            self.busy = True
            # Answer on a separate thread so the keyboard listener never blocks
            threading.Thread(
                target=self.process_text,
                args=(text, self.model, screenshot_base64, command == '/search', command),
                daemon=True,
            ).start()

    def process_text(self, text, model, screenshot_base64=None, search=False, command='/a'):
        label = None  # The status label currently on screen
        trace = None
        try:
            self.type_output(' ...\n')
            prompt = text.strip()
            image_base64 = screenshot_base64
            image = describe_image(screenshot_base64, 'screenshot')

            if '[IMAGE:' in prompt:
                before, rest = prompt.split('[IMAGE:', 1)
                image_base64, after = rest.split(']', 1)
                prompt = (before + after).strip()
                image = describe_image(image_base64, 'pasted')

            self.request_count += 1
            use_files = command == '/files' or (FILES_ALWAYS and command in ('/a', '/see'))
            trace = RequestTrace(command, 'search' if search else model, prompt,
                                 image if not search else None, LOG_PROMPTS, files=use_files)
            if search:
                events = search_stream(prompt)  # Search ignores pasted images
            elif use_files:
                events = files_stream(model, prompt, image_base64)
            else:
                events = api_stream(model, prompt, image_base64)

            answer_started = False
            for kind, value in events:
                trace.event(kind, value)
                if kind not in STATUS_LABELS and kind != TEXT:
                    continue  # Log details only
                if kind in STATUS_LABELS:
                    if not answer_started and label != STATUS_LABELS[kind]:
                        if label:
                            self.erase(len(label))
                        label = STATUS_LABELS[kind]
                        self.type_output(label)
                else:
                    if label:
                        self.erase(len(label))
                        label = None
                    answer_started = True
                    typing_started = time.monotonic()
                    self.type_output(value)
                    trace.add_typing(time.monotonic() - typing_started)
            if label:
                self.erase(len(label))
                label = None
            trace.finish()
        except Exception as e:
            log.exception('Error while answering')
            if trace:
                trace.finish(exception=e)
            try:
                if label:
                    self.erase(len(label))
                self.type_output(f' (TypeGPT error, details in {LOG_FILE.name})')
            except Exception:
                log.exception('Could not type the error message')
        finally:
            self.busy = False

    def erase(self, count):
        for _ in range(count):
            self.keyboard_controller.press(keyboard.Key.backspace)
            self.keyboard_controller.release(keyboard.Key.backspace)

    def type_output(self, text):
        if text == ' ...\n':  # Shows the prompt was sent
            for _ in range(4):
                self.keyboard_controller.press('.')
                self.keyboard_controller.release('.')
            self.keyboard_controller.press(keyboard.Key.enter)
            self.keyboard_controller.release(keyboard.Key.enter)
        else:
            # Normal text output
            for char in text:
                key = CONTROL_KEYS.get(char, char)
                try:
                    self.keyboard_controller.press(key)
                    self.keyboard_controller.release(key)
                except Exception:
                    log.warning('Could not type %r, skipped it', char)

    def restart(self):
        log.info('command /restart')
        self.type_output(' ...restarting.')
        self.should_restart = True
        self.should_quit = True

    def run(self):
        log_startup(self.model)
        crash_times = []
        while not self.should_quit:
            try:
                with SafeListener(on_press=self.on_press, on_release=self.on_release) as listener:
                    log.info('keyboard listener started')
                    listener.join()
                log.info('keyboard listener stopped')
            except Exception:
                log.exception('Keyboard listener stopped unexpectedly')
            if self.should_quit:
                break

            # The listener died; start a new one unless it keeps dying
            now = time.time()
            crash_times = [t for t in crash_times if now - t < 60] + [now]
            if len(crash_times) > 5:
                log.error('Keyboard listener failed %d times in a minute, giving up', len(crash_times))
                sys.exit(EXIT_TOO_MANY_CRASHES)
            self.cancel_input()
            self.special_keys = {'modifier': False, 'shift': False}
            log.info('Restarting keyboard listener')
            time.sleep(1)

        log.info('TypeGPT exiting | reason=%s uptime=%.0fs requests=%d',
                 'restart' if self.should_restart else 'quit',
                 time.monotonic() - self.started_at, self.request_count)
        if self.should_restart:
            sys.exit(EXIT_RESTART)
        sys.exit(0)


def log_startup(model):
    from importlib.metadata import version
    keys = [name for provider, name in api_calls.KEY_NAMES.items() if api_calls.has_key(provider)]
    log.info('TypeGPT started | python=%s platform=%s pynput=%s', platform.python_version(),
             platform.platform(), version('pynput'))
    log.info('config | model=%s models=%s search_model=%s prefer_openrouter=%s log_prompts=%s '
             'system_prompt_chars=%d keys_set=%s',
             model, ','.join(MODELS), SEARCH_MODEL, api_calls.PREFER_OPENROUTER, LOG_PROMPTS,
             len(api_calls.system_prompt), ','.join(keys) or 'none')


def check_permissions():
    if not IS_MAC:
        return
    try:
        from ApplicationServices import AXIsProcessTrusted
    except ImportError:
        return  # Can't check; pynput will still work if access was granted
    if AXIsProcessTrusted():
        log.info('permissions | Accessibility granted')
    else:
        log.error('permissions | Accessibility not granted, exiting')
        print("\nAccessibility Permissions Required!")
        print("\nPlease follow these steps to enable accessibility access:")
        print("1. Open System Settings")
        print("2. Go to Privacy & Security > Accessibility")
        print("3. Add and enable the app you run TypeGPT from (e.g. Terminal)")
        print("4. Also enable it under Privacy & Security > Input Monitoring")
        print("\nAfter granting permissions, please restart the application.")
        sys.exit(EXIT_NO_PERMISSIONS)


def handle_sigterm(signum, frame):
    log.info('TypeGPT exiting | reason=stopped (SIGTERM, e.g. GUI Stop button)')
    sys.exit(0)


if __name__ == "__main__":
    setup_logging()
    signal.signal(signal.SIGTERM, handle_sigterm)
    check_permissions()
    typegpt = TypeGPT()
    typegpt.run()
