#!/bin/bash

while true; do
    python3 TypeGPT.py
    if [ $? -ne 42 ]; then  # If exit code is not 42 (our restart code)
        break              # Exit the loop
    fi
done
