#!/bin/bash
# Sets up TypeGPT's Python environment in .venv
set -e
cd "$(dirname "$0")"

if command -v uv &> /dev/null; then
    echo "Installing with uv..."
    uv sync
else
    echo "uv not found, using python3 -m venv..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install pillow pynput pyperclip requests
fi

if [ ! -f keys.txt ]; then
    cp keys.template.txt keys.txt
    echo "Created keys.txt. Add your API keys to it (or use the GUI's API Keys tab)."
fi

chmod +x run.sh
echo ""
echo "Done. Start TypeGPT with: ./run.sh            (GUI manager)"
echo "                      or: ./run.sh --no-gui   (terminal only)"
echo "macOS: allow your terminal under System Settings > Privacy & Security >"
echo "Accessibility and Input Monitoring (and Screen Recording for /see)."
