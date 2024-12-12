#!/bin/bash

# Activate virtual environment
source myenv/bin/activate

# Check if --no-gui flag is provided
if [ "$1" == "--no-gui" ]; then
    # Run TypeGPT directly with restart capability
    while true; do
        python3 TypeGPT.py
        if [ $? -ne 42 ]; then  # If exit code is not 42 (our restart code)
            break              # Exit the loop
        fi
    done
else
    # Launch the GUI by default
    python3 typegpt_gui.py
fi

# Deactivate virtual environment when done
deactivate
