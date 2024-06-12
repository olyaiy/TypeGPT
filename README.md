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
- `google.generativeai` package

You also need to have an API key from OpenAI for ChatGPT access. You can get yours at https://openai.com/api/

## Installation
Open your terminal/shell, and enter the following commands.


1. Clone the repository:
``` git clone https://github.com/olyaiy/TypeGPT.git ```

3. Navigate into the project directory:
```cd TypeGPT```

4. Give execute permission, and run the install.sh file:

on mac
```chmod +x install.sh```


```chmod +x run.sh```


```./install.sh``` 


## Running the program:
### Run using the provided executable (will allow the program to run in the background ###


```./run.sh```

To manage the program, use:
```ps aux | grep TypeGPT.py```

and in order to stop the program from running, grab the PID you're shown when you run the command above (a 5 digit number associated with the process), and type the following:
```kill -9 12812``` 

here our PID is 12812 for example.


## Usage ##
Use the following keyboard shortcuts in ANY TEXT FIELD ( search bars, google docs, code editors, etc) to interact with the application:

- `/ask`: Follow this command with your prompt and press ```Cmd+Shift+Enter``` to send it. You can also paste the clipboard content using Cmmd+V. Anything you paste will be included in your prompt.


- `/see`: Uses clipboard content as the prompt. Preview the first 9 words, then press Cmd+Shift+Enter.


- `/stop`: Stop listening. Everytime you type `/ask` or `/see` the program starts listening for Cmmd+shift+Enter to send a prompt to the OpenAI API. When you type /stop, the program will stop listening. This is incase you start a prompt but change your mind.


- `/chatgpt`: Switch to ChatGPT model.
- `/gemini`: Switch to Google Gemini model.
- `/check`: Check which model is currently active.
- `/quitt`: To quit the program. 



- `Shift + Cmd + Enter`: Send the text to ChatGPT when in listening mode.

Ensure you set your `OPENAI_API_KEY` and `GEMINI_API_KEY` by modifying the `keys.txt` file in the project directory. Update this file with your actual API keys:

OPENAI_API_KEY=your-openai-key-here
GEMINI_API_KEY=your-gemini-key-here

This file is critical for the application to function correctly, so be sure to update it before running the program.

## Configuration

Modify the `system_prompt.txt` file to customize the behavior and responses of your AI based on your needs. 
You can also change the version of Gemini or ChatGPT in the apicalls.py file. Currently the default is set to gpt-4-turbo and gemini-1.5-flash.

## Contributing

Contributions are very welcome! Please fork the repository and submit pull requests with your proposed changes.

## Future Plans
I plan on adding support for other API's (Gemini, Claude, Olama) as well as a user-friendly GUI to pass your api key's into. If you have any further ideas, I'd love to hear them!


## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.











