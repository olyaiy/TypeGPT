#!/bin/bash
cd "$(dirname "$0")"
PY=.venv/bin/python
if [ ! -x "$PY" ]; then
    echo "No .venv found. Run ./install.sh first."
    exit 1
fi
if [ "$1" == "--no-gui" ]; then
    exec "$PY" TypeGPT.py
else
    exec "$PY" typegpt_gui.py
fi
