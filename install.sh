#!/bin/bash

set -e
cd "$(dirname "$0")"

echo "Starting TypeGPT installation..."

# uv installs Python 3.12 (with Tkinter) and all dependencies
if ! command -v uv &> /dev/null && [ ! -x "$HOME/.local/bin/uv" ]; then
    echo "uv is required (https://docs.astral.sh/uv/)."
    echo "This runs: curl -LsSf https://astral.sh/uv/install.sh | sh"
    read -r -p "Install uv now? (y/n) " response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        echo "Please install uv and run this script again."
        exit 1
    fi
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"

echo "Installing Python packages..."
"$UV" sync

# Ollama is only needed for local models
if ! command -v ollama &> /dev/null; then
    echo "Note: Ollama is not installed. It's only needed if you add local models to models.toml."
    echo "Get it at https://ollama.com/download"
fi

# Create template files if they don't exist
if [ ! -f keys.txt ]; then
    echo "Creating keys.txt from keys.template.txt..."
    cp keys.template.txt keys.txt
fi

if [ ! -f system_prompt.txt ]; then
    echo "Creating empty system_prompt.txt..."
    touch system_prompt.txt
fi

chmod +x run.sh

# `typegpt` command (uv's installer already puts ~/.local/bin on your PATH)
mkdir -p "$HOME/.local/bin"
ln -sf "$(pwd)/run.sh" "$HOME/.local/bin/typegpt"

echo "Installation completed successfully!"
echo "Please follow these steps to complete setup:"
echo "1. Add your API keys to keys.txt (or in the GUI's API Keys tab)"
echo "2. macOS: allow your terminal in System Settings > Privacy & Security > Accessibility and Input Monitoring"
echo "3. Start the program using: typegpt   (or typegpt --no-gui)"
