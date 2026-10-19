# TypeGPT

Oct 2026 update: TypeGPT now supports Claude Opus 5.5, Claude Sonnet 5.5, GPT-6.1 Sol, DeepSeek Flash and Gemini 4 Argon, plus every model on [OpenRouter](https://openrouter.ai/models) with a single key. Models are configured in `models.toml`, installation uses [uv](https://docs.astral.sh/uv/), and input handling got a round of fixes (spaces, backspace, `/` in prompts, Esc, Ctrl on Windows/Linux, and `/see` screenshots).

TypeGPT is a Python application that allows you to invoke various AI's and LLM's from any text field in your operating system. Whether you're in a chat app, document, or code editor, you can seamlessly interact with Claude, ChatGPT, DeepSeek, Google Gemini, or local models with Ollama, using keyboard shortcuts.


https://github.com/olyaiy/TypeGPT/assets/97487352/d92022db-171f-4b3e-804b-320fe0a94156


## Features

- **Global Accessibility**: Invoke AI models from any text input field across your system.
- **Multiple AI Models**: Claude, GPT, DeepSeek, Gemini, any model on OpenRouter, and local models through Ollama.
- **Configurable Models**: Add or change models in `models.toml` without touching code.
- **GUI Manager**: Easy-to-use interface for managing API keys and program status.
- **Keyboard Shortcuts**: Use simple keyboard shortcuts to communicate with AI models.
- **Clipboard Integration**: Utilize the clipboard for larger text inputs and image pasting.
- **Screenshot Capability**: Capture and include screenshots in your queries.

## Models

| Command | Model | Provider |
|---|---|---|
| `/opus` (default, also `/claude`) | `claude-opus-5-5` | Anthropic |
| `/sonnet` | `claude-sonnet-5-5` | Anthropic |
| `/gpt` (also `/chatgpt`) | `gpt-6.1-sol` | OpenAI |
| `/deepseek` (also `/flash`, `/dsflash`) | `deepseek-flash` | DeepSeek |
| `/dspro` | `deepseek-v4-pro` | DeepSeek |
| `/gemini` | `gemini-4-argon` | Google |

To add a model, add an entry to `models.toml`:

```toml
[models.haiku]
provider = "anthropic"   # anthropic | openai | deepseek | gemini | ollama
model = "claude-haiku-5-5"
```

It's then available as `/haiku`. Any model you've pulled in Ollama works the same way with `provider = "ollama"`.

### File access

Give the model read-only access to folders, such as your course notes, and it can list, search and read the files (PDFs and text files) to answer you, citing the file and page. Set the folders in `models.local.toml` (your personal settings file, ignored by git; anything in it overrides `models.toml`):

```toml
[files]
folders = ["~/Documents/course-notes"]
always = true   # every /a and /see question can use the files; false = only /files
```

Then type `/files` (or just `/a` with `always = true`), your question, and `Cmd+Shift+Enter`. You'll see `(reading files)` while it looks. Nothing outside the listed folders is reachable, and it can't change or delete anything. File access works with DeepSeek models, or with any model when `OPENROUTER_API_KEY` is set (Claude, GPT and Gemini go through OpenRouter for this).

### Web search

`/search` answers with live web results using DeepSeek's built-in web search (`deepseek-v4-pro`). Type `/search`, your question, then `Cmd+Shift+Enter`. It always uses DeepSeek, whichever model is selected, and needs `DEEPSEEK_API_KEY`. While it works you'll see `(thinking)` and `(searching)`. DeepSeek charges per search (about $0.75 per 1,000 searches) on top of tokens. Change the model with `search_model` in `models.toml`.

### OpenRouter

With an `OPENROUTER_API_KEY`, one key covers every model:

- **The commands above:** each model has an `openrouter` ID in `models.toml`. If you don't have that provider's own key, TypeGPT sends it through OpenRouter instead. Set `prefer_openrouter = true` to always use OpenRouter.
- **Any other model:** type `/model`, then an OpenRouter model ID such as `meta-llama/llama-4-maverick` or `anthropic/claude-haiku-5.5`, then `Cmd+Shift+Enter`. Browse IDs at https://openrouter.ai/models.
- To give an OpenRouter model its own command, add it to `models.toml` with `provider = "openrouter"`.

## Installation

Requires macOS, Windows or Linux. [uv](https://docs.astral.sh/uv/) installs Python 3.12 and all dependencies for you.

```bash
git clone https://github.com/olyaiy/TypeGPT.git
cd TypeGPT
./install.sh
```

`install.sh` offers to install uv if you don't have it, runs `uv sync`, and creates `keys.txt` from `keys.template.txt`. On Windows, install uv yourself and run `uv sync`.

### API keys

Add the keys for the providers you use to `keys.txt` (or in the GUI's API Keys tab). You only need keys for the models you use, and an OpenRouter key alone works for all of them:

```txt
OPENROUTER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DEEPSEEK_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

Get them at:
- OpenRouter: https://openrouter.ai/keys
- Claude: https://platform.claude.com/
- OpenAI: https://platform.openai.com/
- DeepSeek: https://platform.deepseek.com/
- Google Gemini: https://ai.google.dev/aistudio
- Local models: install [Ollama](https://ollama.com/download) and keep it running (http://localhost:11434)

`keys.txt` is gitignored.

### macOS permissions
TypeGPT needs to watch and type keystrokes:

1. Open System Settings > Privacy & Security
2. Under **Accessibility** and **Input Monitoring**, add and enable the app you run TypeGPT from (e.g. Terminal, iTerm, or VS Code)
   - For `/see`, also enable it under **Screen Recording**
3. Restart TypeGPT

TypeGPT checks Accessibility access on startup and tells you if it's missing.

## Running the Program

### Option 1: Using the GUI Manager
```bash
./run.sh
```
1. Enter your API keys in the "API Keys" tab
2. Use the "Program Status" tab to start/stop TypeGPT

### Option 2: Direct Launch
```bash
./run.sh --no-gui
```

## Usage
Use the following commands in any text field:

### Basic Commands
- `/a`: Start a prompt
- `/see`: Capture a screenshot and start a prompt about it
- `/search`: Ask a question with web search (DeepSeek, needs `DEEPSEEK_API_KEY`)
- `/files`: Ask a question the model can answer from your own files (see [File access](#file-access))
- `/stop`: Stop listening
- `/quit`: Quit the program
- `/restart`: Restart the program
- `/check`: Check which model is currently active
- `/help`: Type out the list of commands and models
- `/<model>`: Switch models (see [Models](#models))
- `/model`: Type any OpenRouter model ID, then `Cmd+Shift+Enter` to switch to it

### Sending Queries
1. Type `/a` (or `/see` to include a screenshot)
2. Type your prompt. You can use `/`, spaces, and Backspace normally
3. Press `Cmd+Shift+Enter` (Mac) or `Ctrl+Shift+Enter` (Windows/Linux) to send
4. The answer is typed out as it arrives. While the model is thinking, `(thinking)` is shown and then erased when the answer starts

### Keyboard Controls
- Send Query: `Cmd+Shift+Enter` (Mac) or `Ctrl+Shift+Enter` (Windows/Linux)
- Cancel Input: `Esc`
- Paste Content: `Cmd/Ctrl+V` (text or images)

## Configuration Files
1. `keys.txt`: API keys (see above)
2. `models.toml`: Available models, commands, and settings. Put personal overrides (your folders, a different default model) in `models.local.toml`, which git ignores
3. `system_prompt.txt`: System prompt sent to every model. By default it asks for plain text only (no Markdown), since replies are typed into ordinary text fields
4. `typegpt.log`: Log of every request (model, routing, timing, thinking and search time, token usage, request IDs, errors), commands, and crashes. Prompts and answers are only logged if you set `log_prompts = true` in `models.toml`. Keystrokes are never logged

## Contributing

Contributions are very welcome! Please fork the repository and submit pull requests with your proposed changes.

## Future Plans
We plan on adding support for more AI models and improving the user interface. If you have any further ideas, we'd love to hear them!

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.
