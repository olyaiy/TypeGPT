from pynput import keyboard
import pyperclip
from apicalls import query_openai, query_gemini

listening = False
captured_text = ''
command_pressed = False
shift_pressed = False
keyboard_controller = keyboard.Controller()
mode = None
model = 'chatgpt'

def api_call(text):
    global model

    if model == 'chatgpt':
        return query_openai(text)
    elif model == 'gemini':
        return query_gemini(text)

def on_press(key):
    # Declare global variables to modify them inside the function
    global listening, captured_text, command_pressed, shift_pressed, mode, model
    
    try:
        # Check special keys
        if key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
            command_pressed = True
        elif key == keyboard.Key.shift:
            shift_pressed = True

        # Handle character keys
        if hasattr(key, 'char'):

            # If the character is '/', check the listening state            
            if key.char == '/':
                listening = True  # Set listening to True or keep it True
                captured_text = '/'  # Start or restart capturing text with '/'

            # If in listening mode and another character is pressed
            elif listening:

                if captured_text is not None and key.char is not None:
                    # Add the character to the captured text
                    captured_text += key.char

                if captured_text == '/quit':
                    mode = 'quit'
                    listening = False
                    listener.stop()  # Stop the listener directly
                    type_text(' ...quitting.')
                    return False  # Additionally return False to terminate the loop

                # Check if the captured text is '/ask'
                if captured_text == '/ask':
                    mode = 'line'  # Set the mode to 'line' which might affect subsequent processing
                    type_text(": ")

                # Check if the captured text is '/see'
                elif captured_text == '/see':
                    mode = 'all'  # Set the mode to 'all' which might affect subsequent processing
                    captured_text = pyperclip.paste()  # Get text from clipboard

                    if len(captured_text) >= 10:
                        type_text(" (" + captured_text[:10] + "...)")
                    else:
                        type_text(" " + captured_text +  "...")


                elif captured_text == '/stop':
                    # If '/stop' is typed, stop listening and reset variables
                    listening = False
                    captured_text = ''
                    mode = None
                    type_text(' ..stopped.')  # Provide feedback to the user that listening has stopped

                elif captured_text == '/chatgpt' or captured_text == '/chatGPT' or captured_text == '/chat GPT' :
                    model = 'chatgpt'  
                    mode = None
                    listening = False
                    type_text(' ... ChatGPT selected.')

                elif captured_text == '/Gemini' or captured_text == '/gemini':
                    model = 'gemini' 
                    mode = None
                    listening = False
                    type_text(' ... Gemini selected.')

                elif captured_text == '/check':
                    type_text(" "+ model)
                    listening = False
                    mode = None

                



    except AttributeError:
        # Handle the case where key does not have a 'char' attribute
        captured_text = 'input not captured. Just tell user: "Try again."'




def on_release(key):
    # Access global variables that are used to control the flow and state of the application
    global listening, captured_text, command_pressed, shift_pressed, mode
    
    # Stop the listener if the escape key is pressed
    if key == keyboard.Key.esc:
        return False
    
    # Reset command key flag when either left or right command keys are released
    if key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
        command_pressed = False
    
    # Reset shift key flag when the shift key is released
    if key == keyboard.Key.shift:
        shift_pressed = False
    
    # Check if the enter key is released
    if key == keyboard.Key.enter:
        # Check if both command and shift keys were pressed together
        if command_pressed and shift_pressed:
            # Check if the application is in "listening" mode
            if listening:
                # Process based on the current mode
                if mode == 'line':

                    # Handle the line mode where only the current line is processed
                    query = captured_text[5:]  # Remove '/ask' from the start
                    keyboard_controller.type('... \n')  # Simulate typing
                    response = api_call(query.strip())  # Get response from chatGPT
                    type_text(response)  # Type out the response

                elif mode == 'all':
                    # Assuming you want to process the entire captured text
                    query = captured_text  # This should be set based on your specific needs
                    keyboard_controller.type(' -> \n')  # Simulate typing
                    response = api_call(query.strip())  # Get response from chatGPT
                    keyboard_controller.type(response)  # Type out the responseHello! How can I assist you today?

                elif mode == 'quit':
                    return False  # Stop the listener and quit the program



                # Reset variables after processing
                listening = False
                captured_text = ''
                mode = None


def type_text(text):
    # Use the pynput keyboard controller to simulate typing the provided text
    keyboard_controller.type(text)

# Set up a keyboard listener to handle key presses and releases
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    # Start the listener and continue until it stops (e.g., when Escape is pressed)
    listener.join()


