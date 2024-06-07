# TypeGPT

June 7, 2024 update: added the ability to switch to select Google Gemini. Support for other LLMs on the way!

TypeGPT is a Python application that allows you to invoke ChatGPT or Google Gemini from any text field in your operating system. Whether you're in a chat app, document, or code editor, you can seamlessly interact with ChatGPT using keyboard shortcuts.


https://github.com/olyaiy/TypeGPT/assets/97487352/d92022db-171f-4b3e-804b-320fe0a94156





## Features

- **Global Accessibility**: Invoke ChatGPT from any text input field across your system.
- **Keyboard Shortcuts**: Use simple keyboard shortcuts to communicate with ChatGPT.
- **Clipboard Integration**: Optionally utilize the clipboard for larger text inputs.

## Prerequisites

Before you can run the application, ensure you have the following installed:
- Python 3.x
- `pynput` package
- `requests` package
- `pyperclip` package

You also need to have an API key from OpenAI for ChatGPT access. You can get yours at https://openai.com/api/

## Installation
Open your terminal/shell, and enter the following commands.


1. Clone the repository:
``` git clone https://github.com/yourusername/chatgpt-anywhere.git ```

3. Navigate into the project directory:
```cd TypeGPT```

4. Install the required packages:
```pip install pynput requests pyperclip```

## Running the program:
### Option 1 - Run the program normally ###
```python3 textfieldgpt.py```

### Option 2 - Run the program in the background ###
This will allow you to have the program running, even when the terminal is closed:
```nohup python3 textfieldgpt.py &```
To manage the process, use:
```ps aux | grep textfieldgpt.py```
and in order to stop the program from running, grab the PID you're shown when you run the command above (a 5 digit number associated with the process), and type the following:
```kill -9 12812``` 
here our PID is 12812 for example.


## Usage ##
Use the following keyboard shortcuts in ANY TEXT FIELD ( search bars, google docs, code editors, etc) to interact with the application:

- `/ask`: Follow this command with your prompt and press ```Cmd+Shift+Enter``` to send it.


- `/see`: Uses clipboard content as the prompt. Preview the first 9 words, then press Cmd+Shift+Enter.


- `/stop`: Stop listening. Everytime you type `/ask` or `/see` the program starts listening for Cmmd+shift+Enter to send a prompt to the OpenAI API. When you type /stop, the program will stop listening. This is incase you start a prompt but change your mind.

- `/chatgpt`: Switch to ChatGPT model.
- `/gemini`: Switch to Google Gemini model.
- `/check`: Check which model is currently active.


- `Shift + Cmd + Enter`: Send the text to ChatGPT when in listening mode.

Ensure you set your `API_KEY` in the environment variables for the application to function correctly.
On macOS and Linux, add this line to .bashrc or .zshrc:
```export API_KEY='your_api_key_here'```
(If you don't know how, ask chatGPT to show you).

## Configuration

Modify the `system_prompt` in the script to customize the behavior and responses of ChatGPT based on your needs.

## Contributing

Contributions are very welcome! Please fork the repository and submit pull requests with your proposed changes.

## Future Plans
I plan on adding support for other API's (Gemini, Claude, Olama) as well as a user-friendly GUI to pass your api key's into. If you have any further ideas, I'd love to hear them!


## License

Distributed under the MIT License. See `LICENSE` for more information.











