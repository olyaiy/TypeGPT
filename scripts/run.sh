#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Print debug information
echo "Current directory: $(pwd)"
echo "Script location: $0"

# Change to the project root directory
cd "$(dirname "$0")/.."

echo "Changed to directory: $(pwd)"

# Check if the virtual environment exists
if [ ! -d "myenv" ]; then
    echo "Virtual environment not found. Please run the install script first."
    exit 1
fi

# Activate the virtual environment
source myenv/bin/activate

# Check if the main Python file exists
if [ ! -f "src/main.py" ]; then
    echo "Error: src/main.py not found. Directory contents:"
    ls -R src
    exit 1
fi

# Run the program in the background using the Python from the virtual environment
nohup myenv/bin/python -m src.main > typegpt.log 2>&1 &

# Inform the user
echo "TypeGPT is running in the background. Output is being logged to typegpt.log"
echo "To stop the program, find its PID using 'ps aux | grep main.py' and then use 'kill <PID>'"