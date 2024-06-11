#!/bin/bash

## NOTE: when running ./install.sh, you may need: sudo apt install python3.10-venv
## Also if not already installed, you may need this as well: sudo apt-get install python3-dev

# Create a virtual environment
python3 -m venv myenv

# Activate the virtual environment
source myenv/bin/activate

# Install the required packages
pip install pynput requests pyperclip google.generativeai

# Deactivate the virtual environment
deactivate

echo "Installation completed. You can now run the program with 'sh run.sh'"
