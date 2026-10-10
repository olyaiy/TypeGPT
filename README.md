# TypeGPT

Use Claude, ChatGPT, Gemini or a local Llama model from any text field on your computer.
Select some text, press **Cmd+Shift+Space**, and the reply is pasted in.

https://github.com/olyaiy/TypeGPT/assets/97487352/d92022db-171f-4b3e-804b-320fe0a94156

## How it works

1. Write your prompt in any app (email, Slack, Notes, a code editor...).
2. Select it.
3. Press **Cmd+Shift+Space** (Ctrl+Shift+Space on Windows/Linux).
4. TypeGPT copies the selection, asks the model, and pastes the answer below your prompt.

Your clipboard is restored afterwards. Errors show up as a notification and in the terminal,
never inside your document.

## Commands

Start the selected text with any of these:

| Command | What it does |
| --- | --- |
| `/claude` | Use Claude (`claude-opus-5-5`) |
| `/gpt` or `/chatgpt` | Use OpenAI (`gpt-6.1-sol`) |
| `/gemini` | Use Gemini (`gemini-3.8-flash`) |
| `/llama` | Use a local model through Ollama (`llama3`) |
| `/see` | Attach a screenshot of your screen |
| `/clip` | Attach the image currently on your clipboard |

Combine them: `/gemini /see what's wrong with this chart?`

Select **only** a model command (e.g. `/gpt`) and press the hotkey to make it the default for the session.

## Setup

```bash
git clone https://github.com/olyaiy/TypeGPT.git
cd TypeGPT
./install.sh        # uses uv if installed, otherwise python3 -m venv
./run.sh            # GUI manager (API keys + start/stop)
./run.sh --no-gui   # terminal only
```

Add your API keys in the GUI's **API Keys** tab, or copy `keys.template.txt` to `keys.txt` and fill it in.
You only need keys for the providers you use. Environment variables override `keys.txt`.

### macOS permissions

In **System Settings > Privacy & Security**, allow your terminal app (or Python) under:

- **Accessibility** and **Input Monitoring**: to see the hotkey and send Cmd+C / Cmd+V
- **Screen Recording**: only needed for `/see`

Restart TypeGPT after granting them.

## Configuration

Everything is optional and lives in `keys.txt` (or environment variables):

| Setting | Default | |
| --- | --- | --- |
| `TYPEGPT_DEFAULT_PROVIDER` | `claude` | `claude`, `chatgpt`, `gemini` or `llama3` |
| `TYPEGPT_HOTKEY` | `<cmd>+<shift>+<space>` | [pynput hotkey syntax](https://pynput.readthedocs.io/en/latest/keyboard.html#global-hotkeys) |
| `TYPEGPT_OUTPUT_MODE` | `append` | `append` keeps your prompt, `replace` swaps it for the answer |
| `ANTHROPIC_MODEL` / `OPENAI_MODEL` / `GEMINI_MODEL` / `OLLAMA_MODEL` | see table above | model IDs |
| `TYPEGPT_TIMEOUT` | `120` | seconds per request |
| `TYPEGPT_MAX_TOKENS` | `4096` | Claude reply limit |

Edit `system_prompt.txt` to change how the models answer.

## Project layout

- `TypeGPT.py`: hotkey listener and the copy, ask, paste flow (requests run on a worker thread)
- `api_calls.py`: one function per provider, all plain HTTPS calls
- `config.py`: settings, API keys and the system prompt
- `typegpt_gui.py`: Tkinter manager for keys and start/stop

## Privacy

TypeGPT listens for its hotkey system-wide, but it only reads what you select and send.
It does not record your typing.

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
