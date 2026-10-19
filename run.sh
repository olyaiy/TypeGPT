#!/bin/bash

# Resolve symlinks so the `typegpt` command works from anywhere
cd "$(dirname "$(readlink -f "$0")")"

UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
if [ ! -x "$UV" ]; then
    echo "uv is not installed. Run ./install.sh first."
    exit 1
fi

# --index: read the image-heavy PDF pages in your file folders now (OCR), then exit
if [ "$1" == "--index" ]; then
    "$UV" run python -c "import logging, api_calls; logging.basicConfig(level=logging.INFO, format='%(message)s'); logging.getLogger('httpx').setLevel(logging.WARNING); api_calls.FILE_LIBRARY.index_ocr()"
    exit $?
fi

# Check if --no-gui flag is provided
if [ "$1" == "--no-gui" ]; then
    # Run TypeGPT directly, relaunching it after /restart or a crash
    crashes=0
    while true; do
        started=$(date +%s)
        "$UV" run python TypeGPT.py
        code=$?
        case $code in
            42) crashes=0 ;;                    # /restart
            0|2|3|130|143) break ;;             # quit, gave up, no permissions, Ctrl+C, stopped
            *)
                # Crashed: relaunch, unless it keeps crashing
                if [ $(( $(date +%s) - started )) -gt 60 ]; then crashes=0; fi
                crashes=$((crashes + 1))
                if [ $crashes -gt 5 ]; then
                    echo "TypeGPT keeps crashing. Details are in typegpt.log."
                    break
                fi
                echo "TypeGPT stopped unexpectedly (exit code $code). Restarting..."
                sleep 2
                ;;
        esac
    done
else
    # Launch the GUI by default
    "$UV" run python typegpt_gui.py
fi
