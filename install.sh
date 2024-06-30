#!/bin/bash

## NOTE: when running ./install.sh, you may need: sudo apt install python3.10-venv
## Also if not already installed, you may need this as well: sudo apt-get install python3-dev

# Create a virtual environment
python3 -m venv myenv

# Activate the virtual environment
source myenv/bin/activate

# Install the required packages
pip install pynput requests pyperclip google-generativeai anthropic pillow pyautogui

# Check if Ollama is installed (for Llama3)
if ! command -v ollama &> /dev/null
then
    echo "Ollama is not installed. Please install Ollama for Llama3 support."
    echo "Visit https://github.com/jmorganca/ollama for installation instructions."
    echo "After installing Ollama, run this script again to complete the setup."
    echo "Exiting without deactivating the virtual environment."
    exit 1
fi

# If we reach this point, all installations were successful
deactivate

echo "Installation completed successfully. You can now run the program with 'sh run.sh'"
echo "Make sure to update your API keys in the keys.txt file before running the program."