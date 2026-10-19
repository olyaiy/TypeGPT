import pyautogui
import base64
from io import BytesIO
from pynput import keyboard
import pyperclip
from api_calls import (api_stream, search_stream, openrouter_model_exists, DEFAULT_MODEL, MODELS,
                       MODEL_COMMANDS, SEARCH_MODEL, THINKING, SEARCHING)
import sys
from PIL import Image, ImageGrab
import io
import platform
import threading

IS_MAC = platform.system() == 'Darwin'

# Cmd on macOS, Ctrl on Windows/Linux
MODIFIER_KEYS = (
    {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r} if IS_MAC
    else {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r}
)
SHIFT_KEYS = {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r}
PASTE_CHARS = ('v', 'V', '\x16')  # '\x16' is what Ctrl+V reports on some platforms
# Shown while the model works, erased when the answer starts
STATUS_LABELS = {THINKING: '(thinking)', SEARCHING: '(searching)'}
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
        self.commands = {
            '/quit': self.quit,
            '/stop': self.stop_listening,
            '/a': lambda: self.set_mode('line'),
            '/see': self.capture_screenshot,
            '/search': lambda: self.set_mode('search'),
            '/model': lambda: self.set_mode('model'),
            '/check': self.check_model,
            '/restart': self.restart,
            '/help': self.show_help,
        }
        for command, model in MODEL_COMMANDS.items():
            self.commands[f'/{command}'] = lambda model=model: self.select_model(model)

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

    def on_release(self, key, injected=False):
        if injected:
            return True
        self.handle_special_keys(key, pressed=False)

        if key == keyboard.Key.esc:
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
            self.type_output("(image pasted)")
        else:
            self.captured_text += pyperclip.paste()

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
        try:
            self.screenshot = pyautogui.screenshot()
        except Exception:
            # Usually missing Screen Recording permission on macOS
            self.cancel_input()
            self.type_output(" ...screenshot failed. Allow Screen Recording for this app in System Settings.")
            return
        buffered = BytesIO()
        self.screenshot.save(buffered, format="PNG")
        self.screenshot_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        self.type_output(" ss captured: ")
        self.mode = 'screenshot'

    def quit(self):
        self.type_output(' ...quitting.')
        self.should_quit = True  # Set the flag to quit

    def stop_listening(self):
        self.cancel_input()
        self.type_output(' ...stopped.')

    def cancel_input(self):
        self.listening = False
        self.captured_text = ''
        self.mode = None
        self.screenshot = None
        self.screenshot_base64 = None

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'line':
            self.type_output(": ")
        elif mode == 'model':
            self.type_output(" model: ")
        elif mode == 'search':
            self.type_output(" search: ")

    def select_model(self, model):
        self.model = model
        self.listening = False
        self.type_output(f' ... {model.capitalize()} selected.')

    def choose_model(self, name):
        self.listening = False
        self.mode = None
        if name in MODEL_COMMANDS:
            self.select_model(MODEL_COMMANDS[name])
        elif openrouter_model_exists(name):
            self.model = name
            self.type_output(f' ... {name} selected (OpenRouter).')
        else:
            self.type_output(f' ... unknown model: {name}')

    def show_help(self):
        self.listening = False
        self.mode = None
        lines = [
            '',
            'TypeGPT commands:',
            f'/a  ask a question, then {SEND_KEYS} to send',
            f'/see  ask about a screenshot, then {SEND_KEYS} to send',
            f'/search  ask with web search ({SEARCH_MODEL}), then {SEND_KEYS} to send',
            f'/model  type any OpenRouter model ID, then {SEND_KEYS}',
            '/check  show the active model',
            '/stop  cancel input (or press Esc)',
            '/restart  restart TypeGPT',
            '/quit  quit TypeGPT',
            '/help  show this list',
            'Models:',
        ]
        for name, entry in MODELS.items():
            commands = ', '.join(f'/{c}' for c in [name, *entry.get('aliases', [])])
            active = '  (active)' if name == self.model else ''
            lines.append(f'{commands}  {entry["model"]}{active}')
        threading.Thread(target=self.type_output, args=('\n'.join(lines),), daemon=True).start()

    def check_model(self):
        self.type_output(f" -> {self.model} selected.")
        self.listening = False
        self.mode = None

    def process_enter_key(self):
        if self.listening and self.mode == 'model':
            self.choose_model(self.captured_text.strip())
        elif self.listening and self.mode in ['line', 'screenshot', 'search']:
            if self.busy:
                return  # Still answering the previous prompt
            text, screenshot_base64 = self.captured_text, self.screenshot_base64
            search = self.mode == 'search'
            self.cancel_input()
            self.busy = True
            # Answer on a separate thread so the keyboard listener never blocks
            threading.Thread(
                target=self.process_text,
                args=(text, self.model, screenshot_base64, search),
                daemon=True,
            ).start()

    def process_text(self, text, model, screenshot_base64=None, search=False):
        try:
            self.type_output(' ...\n')
            prompt = text.strip()
            image_base64 = screenshot_base64

            if '[IMAGE:' in prompt:
                before, rest = prompt.split('[IMAGE:', 1)
                image_base64, after = rest.split(']', 1)
                prompt = (before + after).strip()

            if search:
                events = search_stream(prompt)  # Search ignores pasted images
            else:
                events = api_stream(model, prompt, image_base64)

            label = None  # The status label currently on screen
            answer_started = False
            for kind, value in events:
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
                    self.type_output(value)
            if label:
                self.erase(len(label))
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
                self.keyboard_controller.press(key)
                self.keyboard_controller.release(key)

    def restart(self):
        self.type_output(' ...restarting.')
        self.should_restart = True
        self.should_quit = True

    def run(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

        if self.should_restart:
            sys.exit(42)  # Special exit code for restart
        elif self.should_quit:
            sys.exit(0)   # Normal exit


def check_permissions():
    if not IS_MAC:
        return
    try:
        from ApplicationServices import AXIsProcessTrusted
    except ImportError:
        return  # Can't check; pynput will still work if access was granted
    if not AXIsProcessTrusted():
        print("\nAccessibility Permissions Required!")
        print("\nPlease follow these steps to enable accessibility access:")
        print("1. Open System Settings")
        print("2. Go to Privacy & Security > Accessibility")
        print("3. Add and enable the app you run TypeGPT from (e.g. Terminal)")
        print("4. Also enable it under Privacy & Security > Input Monitoring")
        print("\nAfter granting permissions, please restart the application.")
        sys.exit(1)


if __name__ == "__main__":
    check_permissions()
    typegpt = TypeGPT()
    typegpt.run()
