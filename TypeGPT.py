from pynput import keyboard
import pyperclip
from api_calls import query_openai, query_gemini


class TypeGPT:
    # Constructor to initialize the application's state
    def __init__(self):
        self.listening = False  # Tracks if the app is actively listening for user commands
        self.captured_text = ''  # Buffer to store text captured from keyboard
        self.command_pressed = False  # Tracks if the control key is pressed
        self.shift_pressed = False  # Tracks if the shift key is pressed
        self.v_pressed = False  # Tracks if the 'v' key is pressed
        self.keyboard_controller = keyboard.Controller()  # Controller for programmatically controlling the keyboard
        self.mode = None  # Mode of operation (line or all text)
        self.model = 'chatgpt'  # Default AI model to use

    # Function to call the appropriate AI model API with the given text
    def api_call(self, text):
        if self.model == 'chatgpt':
            return query_openai(text)
        elif self.model == 'gemini':
            return query_gemini(text)

    # Event handler for when a key is pressed
    def on_press(self, key):
        try:
            self.handle_special_keys(key)  # Handle special keys like control, shift, v
            if hasattr(key, 'char'):
                self.process_character(key)  # Process printable character keys
        except AttributeError:
            self.captured_text = 'input not captured. Try again.'

    # Handles special keys, setting flags based on which keys are pressed
    def handle_special_keys(self, key):
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.cmd_l, keyboard.Key.cmd_r]:
            self.command_pressed = True  # This is the same as saying ctrl pressed
        elif key == keyboard.Key.shift:
            self.shift_pressed = True
        elif hasattr(key, 'char') and key.char == 'v':
            self.v_pressed = True

    # Processes printable characters; listening for commands or updating the buffer
    def process_character(self, key):
        if key.char == '/':
            self.start_listening()  # Start listening for commands on '/'
        elif self.listening:
            self.update_captured_text(key.char)  # Append character to buffer if listening

    # Starts the listening process, initializes the buffer with '/'
    def start_listening(self):
        self.listening = True
        self.captured_text = '/'

    def update_captured_text(self, char):
        if self.command_pressed and self.v_pressed:  # Check if control and v are pressed together (the user pastes text)
            clipboard_content = pyperclip.paste()  # Get content from clipboard
            self.captured_text += clipboard_content  # Append clipboard content to the captured text
            self.v_pressed = False  # Reset the v_pressed flag to avoid repeated pasting
        else:
            self.captured_text += char  # Normal character appending

        # Check if the accumulated text matches any commands
        if self.captured_text in ['/quit', '/stop', '/ask', '/see', '/chatgpt', '/gemini', '/check']:
            self.process_commands()  # Process recognized commands

    # Processes recognized commands and invokes corresponding methods
    def process_commands(self):
        commands = {
            '/quit': self.quit,
            '/stop': self.stop_listening,
            '/ask': self.set_mode_line,
            '/see': self.set_mode_all,
            '/chatgpt': lambda: self.select_model('chatgpt'),
            '/gemini': lambda: self.select_model('gemini'),
            '/check': self.check_model
        }
        command_function = commands.get(self.captured_text)
        if command_function:
            command_function()

    # Quits the app
    def quit(self):
        self.keyboard_controller.type(' ...quitting.')
        return False

    # Stops listening for commands
    def stop_listening(self):
        self.listening = False
        self.captured_text = ''
        self.mode = None
        self.keyboard_controller.type(' ...stopped.')

    # Sets the app to capture only the current line
    def set_mode_line(self):
        self.mode = 'line'
        self.keyboard_controller.type(": ")

    # Sets the app to capture all text in the clipboard
    def set_mode_all(self):
        self.mode = 'all'
        self.captured_text = pyperclip.paste()
        preview = self.captured_text[:10] + "..." if len(self.captured_text) >= 10 else self.captured_text
        self.keyboard_controller.type(" (" + preview + ")")

    # Selects the AI model to use
    def select_model(self, model):
        self.model = model
        self.listening = False
        self.keyboard_controller.type(f' ... {model.capitalize()} selected.')

    # Checks and displays the current AI model
    def check_model(self):
        self.keyboard_controller.type(" -> " + self.model + " selected.")
        self.listening = False
        self.mode = None

    # Event handler for when a key is released
    def on_release(self, key):
        # Check if the escape key is pressed, if so, return False to stop the listener
        if key == keyboard.Key.esc:
            return False
        # Check if either left or right control keys are released, reset the command_pressed flag
        if key in [keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.cmd_l, keyboard.Key.cmd_r]:
            self.command_pressed = False
        # Check if the shift key is released, reset the shift_pressed flag
        if key == keyboard.Key.shift:
            self.shift_pressed = False

        # Check if the enter key is released while both control and shift keys were held down
        if key == keyboard.Key.enter and self.command_pressed and self.shift_pressed:
            self.process_enter_key()  # Invoke method to process the command input

    # Processes the enter key when control+shift+enter are pressed together
    def process_enter_key(self):
        # Check if the app is currently in listening mode and a specific mode is set
        if self.listening and self.mode in ['line', 'all', 'quit']:
            self.process_text(self.captured_text)  # Process the captured text through the AI model
            self.listening = False  # Stop listening after processing

    # Sends the text to the selected AI model and types the response
    def process_text(self, text):
        # start a new line
        self.keyboard_controller.type(' ...\n')
        # call the appropriate AI model API with the text
        response = self.api_call(text.strip())
        # type the response
        self.keyboard_controller.type(response)

    # Starts the keyboard listener
    def run(self):
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()


# Entry point of the application
if __name__ == "__main__":
    typegpt = TypeGPT()
    typegpt.run()
