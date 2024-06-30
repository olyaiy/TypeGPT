# TypeGPT

June 29, 2024 update: Added support for Claude and Llama3 models, along with improved image handling capabilities!

TypeGPT is a Python application that allows you to invoke various AI's and LLM's from any text field in your operating system. Whether you're in a chat app, document, or code editor, you can seamlessly interact with ChatGPT, Google Gemini, Claude, or Llama3 with Ollama, using keyboard shortcuts.


https://github.com/olyaiy/TypeGPT/assets/97487352/d92022db-171f-4b3e-804b-320fe0a94156




## Features

- **Global Accessibility**: Invoke AI models from any text input field across your system.
- **Multiple AI Models**: Support for ChatGPT, Google Gemini, Claude, and Llama3.
- **Keyboard Shortcuts**: Use simple keyboard shortcuts to communicate with AI models.
- **Clipboard Integration**: Utilize the clipboard for larger text inputs and image pasting.
- **Screenshot Capability**: Capture and include screenshots in your queries.

## Prerequisites

Before you can run the application, ensure you have the following installed:
- Python 3.x
- `pynput` package
- `requests` package
- `pyperclip` package
- `google.generativeai` package
- `anthropic` package
- `Pillow` (PIL) package

You also need to have API keys for the AI services you plan to use. You can get yours at:
- ChatGPT: https://openai.com/api/
- Google Gemini: https://ai.google.dev/aistudio
- Claude: https://www.anthropic.com/
- Llama3: Ensure you have Ollama installed and running locally (http://localhost:11434)

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
### Run using the provided executable (will allow the program to run in the background) ###


```./run.sh```

To manage the program, use:
```ps aux | grep TypeGPT.py```

and in order to stop the program from running, grab the PID you're shown when you run the command above (a 5 digit number associated with the process), and type the following:
```kill -9 12812``` 

here our PID is 12812 for example.


## Usage ##
Use the following keyboard shortcuts in ANY TEXT FIELD ( search bars, google docs, code editors, etc) to interact with the application:

- `/ask`: Follow this command with your prompt and press ```Cmd+Shift+Enter``` to send it. You can also paste the clipboard content using Cmmd+V. Anything you paste will be included in your prompt.

- `/see`: Captures a screenshot to include with your next query. Press `Cmd+Shift+Enter` to send the query with the screenshot. You can also type on the same line 

- `/stop`: Stop listening. Everytime you type `/ask` or `/see` the program starts listening for Cmmd+shift+Enter to send a prompt to the selected AI model. When you type /stop, the program will stop listening. This is incase you start a prompt but change your mind.

- `/chatgpt`: Switch to ChatGPT model.
- `/gemini`: Switch to Google Gemini model.
- `/claude`: Switch to Claude model.
- `/llama3`: Switch to Llama3 model.
- `/check`: Check which model is currently active.
- `/quit`: To quit the program. 

- `Shift + Cmd + Enter`: Send the text to the selected AI model when in listening mode.

Ensure you set your API keys by modifying the `keys.txt` file in the project directory. Update this file with your actual API keys:

```
OPENAI_API_KEY=your-openai-key-here
GEMINI_API_KEY=your-gemini-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here
```

This file is critical for the application to function correctly, so be sure to update it before running the program.

## Configuration

Modify the `system_prompt.txt` file to customize the behavior and responses of your AI based on your needs. 
You can also change the versions of the AI models in the `api_calls.py` file. Currently, the defaults are:
- ChatGPT: gpt-4-turbo
- Gemini: gemini-1.0-pro-vision-latest
- Claude: claude-3-5-sonnet-20240620
- Llama3: Uses the local Ollama instance

## Contributing

Contributions are very welcome! Please fork the repository and submit pull requests with your proposed changes.

## Future Plans
We plan on adding support for more AI models and improving the user interface. If you have any further ideas, we'd love to hear them!

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
