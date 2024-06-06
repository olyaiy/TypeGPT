from pynput import keyboard
from requests import post
import pyperclip, os

API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("No API Key set in environment variables.")
listening = False
captured_text = ''
command_pressed = False
shift_pressed = False
keyboard_controller = keyboard.Controller()
mode = None

system_prompt = """
As an embedded assistant in this application, you are accessible from any text field, 
including chat apps, documents, and code editors. 
Respond with concise and clear answers suitable for the context from which you are called. 
Provide brief responses by default. If requested, provide detailed explanations or complete 
coding solutions. When delivering code, present it plainly without syntax 
highlighting or special formatting. 
Avoid self-references and do not use first-person pronouns. 
Your presence should be seamless and unobtrusive, aiming to integrate naturally into the user's workflow without drawing 
attention to yourself. For open ended questions, answer in concise bullet points LIMITED TO 100 WORDS. It is crucial that you follow 
this limit.  
If the user asks for a detailed explanation, you may provide a short paragraph, up to 300 words.  
For coding questions, give just the code requested with no markdown formatting. Just the code by itself.
"""

def on_press(key):
    # Declare global variables to modify them inside the function
    global listening, captured_text, command_pressed, shift_pressed, mode
    
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
                    response = query_chatgpt(query.strip())  # Get response from chatGPT
                    type_text(response)  # Type out the response

                elif mode == 'all':
                    # Assuming you want to process the entire captured text
                    query = captured_text  # This should be set based on your specific needs
                    keyboard_controller.type('... \n')  # Simulate typing
                    response = query_chatgpt(query.strip())  # Get response from chatGPT
                    type_text(response)  # Type out the response


                # Reset variables after processing
                listening = False
                captured_text = ''
                mode = None

def query_chatgpt(text):
    # Define the URL endpoint for the OpenAI API
    url = 'https://api.openai.com/v1/chat/completions'
    
    # Set up headers with the API key for authorization and content type for JSON
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Prepare the data payload with the specific model and conversation context
    data = {
        'model': 'gpt-4-turbo',  # Specifies the model type
        'messages': [
            {"role": "system", "content": system_prompt},  # System-level instruction for chatbot behavior
            {'role': 'user', 'content': text}  # User's query to be processed by the chatbot
        ] 
    }
    
    # Make an HTTP POST request to the API with the prepared headers and data
    response = post(url, json=data, headers=headers)
    return response.json()['choices'][0]['message']['content']

def type_text(text):
    # Use the pynput keyboard controller to simulate typing the provided text
    keyboard_controller.type(text)

# Set up a keyboard listener to handle key presses and releases
with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    # Start the listener and continue until it stops (e.g., when Escape is pressed)
    listener.join()


