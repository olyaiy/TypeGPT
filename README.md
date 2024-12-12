# TypeGPT

Dec 11, 2024 update: Added support for Claude and Llama3 models, along with improved image handling capabilities and a new GUI manager!

TypeGPT is a Python application that allows you to invoke various AI's and LLM's from any text field in your operating system. Whether you're in a chat app, document, or code editor, you can seamlessly interact with ChatGPT, Google Gemini, Claude, or Llama3 with Ollama, using keyboard shortcuts.


https://github.com/olyaiy/TypeGPT/assets/97487352/d92022db-171f-4b3e-804b-320fe0a94156




## Features

- **Global Accessibility**: Invoke AI models from any text input field across your system.
- **Multiple AI Models**: Support for ChatGPT, Google Gemini, Claude, and Llama3.
- **GUI Manager**: Easy-to-use interface for managing API keys and program status.
- **Keyboard Shortcuts**: Use simple keyboard shortcuts to communicate with AI models.
- **Clipboard Integration**: Utilize the clipboard for larger text inputs and image pasting.
- **Screenshot Capability**: Capture and include screenshots in your queries.

## Prerequisites

Before you can run the application, ensure you have the following installed:
- Python 3.x
- Required packages (install via pip):
  ```bash
  pip install pynput requests pyperclip google.generativeai anthropic Pillow tkinter
  ```

You also need to have API keys for the AI services you plan to use. You can get yours at:
- ChatGPT: https://openai.com/api/
- Google Gemini: https://ai.google.dev/aistudio
- Claude: https://www.anthropic.com/
- Llama3: Ensure you have Ollama installed and running locally (http://localhost:11434)

## Installation
1. Clone the repository:
```bash
git clone https://github.com/olyaiy/TypeGPT.git
cd TypeGPT
```

2. Run the GUI manager to set up your API keys:
```bash
python typegpt_gui.py
```

## Running the Program

### Option 1: Using the GUI Manager
1. Launch the GUI manager:
```bash
python typegpt_gui.py
```
2. Enter your API keys in the "API Keys" tab
3. Use the "Program Status" tab to start/stop TypeGPT

### Option 2: Direct Launch
```bash
python TypeGPT.py
```

## Usage
Use the following commands in any text field:

### Basic Commands
- `/a`: Start listening for input (line mode)
- `/see`: Capture screenshot for visual queries
- `/stop`: Stop listening
- `/quit`: Quit the program
- `/restart`: Restart the program

### Model Selection
- `/chatgpt`: Switch to ChatGPT model
- `/gemini`: Switch to Google Gemini model
- `/claude`: Switch to Claude model
- `/llama3`: Switch to Llama3 model
- `/o1`: Switch to OpenAI's O1 model
- `/check`: Check which model is currently active

### Sending Queries
1. Type `/a` to start input mode
2. Type your prompt
3. Press `Cmd+Shift+Enter` (Mac) or `Ctrl+Shift+Enter` (Windows/Linux) to send
4. Wait for the response to be typed out

## Configuration

1. API Keys: Copy `keys.template.txt` to `keys.txt` and update with your API keys. The `keys.txt` file is gitignored for security.

2. System Prompt: Modify the `system_prompt.txt` file to customize the behavior and responses of your AI based on your needs. 

3. AI Model Versions: You can change the versions of the AI models in the `api_calls.py` file. Currently, the defaults are:
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

## Setup

### macOS Users
TypeGPT requires accessibility permissions to monitor keyboard input:

1. When you first run the application, you'll be prompted to grant accessibility permissions
2. Open System Preferences/Settings
3. Navigate to Security & Privacy > Privacy > Accessibility
4. Click the lock icon to make changes
5. Add and enable your Terminal application or Python.app
6. Restart TypeGPT
