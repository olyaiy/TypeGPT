#!/bin/bash

# Activate the virtual environment
source myenv/bin/activate

# Run the program in the background
nohup python3 TypeGPT.py &

# Inform the user
echo "Program is running in the background."
