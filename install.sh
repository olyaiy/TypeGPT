#!/bin/bash

echo "Starting TypeGPT installation..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3 first."
    exit 1
fi

# Check for required system packages
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "Installing required system packages..."
    sudo apt-get update
    sudo apt-get install -y python3-dev python3-tk python3.10-venv
elif [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command -v brew &> /dev/null; then
        echo "Homebrew not found. Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    echo "Installing required system packages..."
    brew install python-tk
fi

# Create a virtual environment
echo "Creating virtual environment..."
python3 -m venv myenv

# Activate the virtual environment
source myenv/bin/activate

# Install the required packages
echo "Installing Python packages..."
pip install --upgrade pip
pip install \
    pynput \
    requests \
    pyperclip \
    google-generativeai \
    anthropic \
    pillow \
    pyautogui \
    tkinter

# Check if Ollama is installed (for Llama3)
if ! command -v ollama &> /dev/null; then
    echo "Ollama is not installed. Please install Ollama for Llama3 support."
    echo "Visit https://github.com/jmorganca/ollama for installation instructions."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Would you like to install Ollama using Homebrew? (y/n)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])+$ ]]; then
            brew install ollama
        fi
    fi
fi

# Create template files if they don't exist
if [ ! -f keys.txt ]; then
    echo "Creating keys.txt template..."
    echo "OPENAI_API_KEY=your_openai_key_here" > keys.txt
    echo "GEMINI_API_KEY=your_gemini_key_here" >> keys.txt
    echo "ANTHROPIC_API_KEY=your_anthropic_key_here" >> keys.txt
fi

if [ ! -f system_prompt.txt ]; then
    echo "Creating empty system_prompt.txt..."
    touch system_prompt.txt
fi

# Make run script executable
chmod +x run.sh

# Deactivate virtual environment
deactivate

echo "Installation completed successfully!"
echo "Please follow these steps to complete setup:"
echo "1. Update your API keys in the keys.txt file"
echo "2. For macOS users: Grant accessibility permissions in System Preferences"
echo "3. Start the program using: sh run.sh"
echo "4. Or use the GUI manager: python typegpt_gui.py"