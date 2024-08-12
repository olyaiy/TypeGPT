#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Check if Python3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python3 is not installed. Please install Python3 and try again."
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "pip3 is not installed. Please install pip3 and try again."
    exit 1
fi

# Create a virtual environment if it doesn't exist
if [ ! -d "myenv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv myenv
fi

# Activate the virtual environment
source myenv/bin/activate

# Install or upgrade pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

# Install the required packages
echo "Installing required packages..."
pip install -r requirements.txt

# Inform the user
echo "Installation complete. You can now run the program using: ./scripts/run.sh"