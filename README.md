# TypeGPT

A Python application that allows you to invoke ChatGPT from any text field in your operating system. Whether you're in a chat app, document, or code editor, you can seamlessly interact with ChatGPT using keyboard shortcuts.

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

You also need to have an API key from OpenAI for ChatGPT access.

## Installation

1. Clone the repository:
``` git clone https://github.com/yourusername/chatgpt-anywhere.git ```

2. Navigate into the project directory:
```cd TypeGPT```

3. Install the required packages:
```pip install pynput requests pyperclip```


Use the following keyboard shortcuts in ANY TEXT FIELD ( search bars, google docs, code editors, etc) to interact with the application:

- `/ask`: anything you type after this command will become the prompt. Press Cmmd+shift+Enter to send the prompt to the OpenAI API.
The response should appear within a few seconds.

- `/see`: Whatever is in your clipboard will become the prompt. You will see a preview of the first 9 words. Press Cmmd+shift+Enter to send your clipboard to chatGPT and the response should appear within a few seconds.

- `/stop`: Stop listening. Everytime you type `/ask` or `/see` the program starts listening for Cmmd+shift+Enter to send a prompt to the OpenAI API. When you type /stop, the program will stop listening. This is incase you start a prompt but change your mind. 

- `Shift + Cmd + Enter`: Send the text to ChatGPT when in listening mode.

Finish this sentance of instructions. add one or two sentances, telling them how to save variables globally and permementantly.
Ensure you set your `API_KEY` in the environment variables for the application to function correctly.
you can set the API_KEY permanently by adding it to your system's environment variables. On macOS and Linux, add the export statement `export API_KEY='your_api_key_here'` to your shell configuration file, such as `.bashrc` or `.zshrc`. (If you don't know how, ask chatGPT to show you).

## Configuration

Modify the `system_prompt` in the script to customize the behavior and responses of ChatGPT based on your needs.

## Contributing

Contributions are very welcome! Please fork the repository and submit pull requests with your proposed changes.

## License

Distributed under the MIT License. See `LICENSE` for more information.











