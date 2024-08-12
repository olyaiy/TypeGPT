import pyautogui
import base64
from io import BytesIO
from pynput import keyboard
import pyperclip
from api_calls import api_call
import sys
from PIL import Image, ImageGrab  # Updated import
import io

class TypeGPT:
    def __init__(self):
        self.listening = False
        self.captured_text = ''
        self.keyboard_controller = keyboard.Controller()
        self.mode = None
        self.model = 'chatgpt'  # Default model
        self.special_keys = {
            'command': False,
            'shift': False,
            'v': False
        }
        self.screenshot = None
        self.screenshot_base64 = None
        self.should_quit = False

    def on_press(self, key):
        try:
            self.handle_special_keys(key, pressed=True)
            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                self.process_character(key.char)
        except AttributeError:
            pass

    def on_release(self, key):
        if key == keyboard.Key.esc:
            return False
        
        self.handle_special_keys(key, pressed=False)

        if (key == keyboard.Key.enter and 
            self.special_keys['command'] and 
            self.special_keys['shift']):
            self.process_enter_key()

        if self.should_quit:
            return False  # This will stop the listener

    def handle_special_keys(self, key, pressed):
        key_mapping = {
            keyboard.Key.cmd: 'command',
            keyboard.Key.shift: 'shift',
        }
        
        if key in key_mapping:
            self.special_keys[key_mapping[key]] = pressed
        elif isinstance(key, keyboard.KeyCode) and key.char == 'v':
            self.special_keys['v'] = pressed

    def process_character(self, char):
        if char == '/':
            self.start_listening()
        elif self.listening:
            self.update_captured_text(char)

    def start_listening(self):
        self.listening = True
        self.captured_text = '/'

    def update_captured_text(self, char):
        if self.special_keys['command'] and self.special_keys['v']:
            self.handle_paste()
        else:
            self.captured_text += char

        self.process_commands()

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
        self.special_keys['v'] = False

    def process_commands(self):
        commands = {
            '/quit': self.quit,
            '/stop': self.stop_listening,
            '/ask': lambda: self.set_mode('line'),
            '/see': self.capture_screenshot,
            '/chatgpt': lambda: self.select_model('chatgpt'),
            '/gemini': lambda: self.select_model('gemini'),
            '/claude': lambda: self.select_model('claude'),
            '/llama3': lambda: self.select_model('llama3'),
            '/check': self.check_model
        }
        
        for cmd, func in commands.items():
            if self.captured_text.endswith(cmd):
                func()
                self.captured_text = ''  # Clear the captured text after processing
                break

    def capture_screenshot(self):
        self.screenshot = pyautogui.screenshot()
        buffered = BytesIO()
        self.screenshot.save(buffered, format="PNG")
        self.screenshot_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        self.type_output(" ss captured: ")
        self.mode = 'screenshot'
        self.captured_text = self.captured_text[:-4]  # Remove '/see' from captured text

    def quit(self):
        self.type_output(' ...quitting.')
        self.should_quit = True  # Set the flag to quit

    def stop_listening(self):
        self.listening = False
        self.captured_text = ''
        self.mode = None
        self.type_output(' ...stopped.')

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'line':
            self.type_output(": ")

    def select_model(self, model):
        if model in ['chatgpt', 'gemini', 'claude', 'llama3']:
            self.model = model
            self.listening = False
            self.type_output(f' ... {model.capitalize()} selected.')
        else:
            self.type_output(f' ... Unsupported model: {model}')

    def check_model(self):
        self.type_output(f" -> {self.model} selected.")
        self.listening = False
        self.mode = None

    def process_enter_key(self):
        if self.listening and self.mode in ['line', 'screenshot', 'quit']:
            self.process_text(self.captured_text)
            self.listening = False

    def process_text(self, text):
        self.type_output(' ...\n')
        prompt = text.strip()
        image_base64 = None
        
        if '[IMAGE:' in prompt:
            parts = prompt.split('[IMAGE:', 1)
            prompt = parts[0]
            image_base64 = parts[1].split(']', 1)[0]
        
        response = api_call(self.model, prompt, image_base64)
        self.type_output(response)
        self.screenshot = None
        self.screenshot_base64 = None
        self.mode = None

    def type_output(self, text):
        for char in text:
            self.keyboard_controller.press(char)
            self.keyboard_controller.release(char)

    def run(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()
        
        if self.should_quit:
            sys.exit(0)  # Properly exit the program

if __name__ == "__main__":
    typegpt = TypeGPT()
    typegpt.run()