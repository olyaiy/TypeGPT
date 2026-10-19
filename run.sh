#!/bin/bash

cd "$(dirname "$0")"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
if [ ! -x "$UV" ]; then
    echo "uv is not installed. Run ./install.sh first."
    exit 1
fi

# Check if --no-gui flag is provided
if [ "$1" == "--no-gui" ]; then
    # Run TypeGPT directly with restart capability
    while true; do
        "$UV" run python TypeGPT.py
        if [ $? -ne 42 ]; then  # If exit code is not 42 (our restart code)
            break              # Exit the loop
        fi
    done
else
    # Launch the GUI by default
    "$UV" run python typegpt_gui.py
fi
