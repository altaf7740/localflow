# LocalFlow

Fully local, Wispr Flow–style dictation for macOS, Windows and Linux that handles Hinglish.
Hold the hotkey (**Right ⌥** on macOS, **Right Ctrl** on Windows/Linux), speak, release — cleaned-up text (Hindi in Roman script) is pasted into the focused app.

## Pipeline

1. **Record** — `sounddevice`, 16 kHz mono, while the hotkey is held.
2. **ASR** — Whisper large-v3-turbo, `language="hi"`: MLX on Apple Silicon, faster-whisper elsewhere
   (CUDA if available, else CPU int8). This recognises Hindi words most
   accurately (output is Devanagari + English).
3. **Cleanup** — `qwen2.5:7b-instruct` via Ollama: transliterates to Roman Hinglish, removes fillers,
   fixes punctuation. Leftover Devanagari triggers a narrow transliteration pass. If Ollama is down
   the raw transcript is pasted.
4. **Paste** — clipboard + ⌘V / Ctrl+V, then the previous clipboard is restored.

Nothing leaves the machine.

## Setup

| | macOS (Apple Silicon) | Windows | Linux |
|---|---|---|---|
| ASR | MLX (GPU) | faster-whisper (CUDA or CPU) | faster-whisper (CUDA or CPU) |
| UI | menu bar | system tray | system tray |
| Hotkey | Right ⌥ | Right Ctrl | Right Ctrl |

Common to all: install [uv](https://docs.astral.sh/uv/) and [Ollama](https://ollama.com), then

```sh
uv sync
ollama pull qwen2.5:7b-instruct
uv run localflow
```

### macOS (Apple Silicon)

Convert Whisper to MLX once (or set `asr_model` to `"mlx-community/whisper-large-v3-turbo"`):

```sh
uv run python scripts/convert_hf_whisper.py openai/whisper-large-v3-turbo models/whisper-large-v3-turbo-mlx
```

Grant your terminal **Microphone**, **Accessibility** and **Input Monitoring** in
System Settings → Privacy & Security, then restart the app.

Intel Macs use faster-whisper (CPU) automatically.

### Windows

- The Whisper model (~1.6 GB) downloads on first launch.
- NVIDIA GPU: install CUDA 12 cuBLAS and cuDNN 9 for GPU speed; without them it falls back to CPU.
- Allow microphone access for desktop apps (Settings → Privacy & security → Microphone).
- Pasting into apps running as Administrator requires running LocalFlow as Administrator.

### Linux

- **X11 only.** Wayland blocks global hotkeys and simulated keystrokes; log in to an X11 session.
- System packages (Debian/Ubuntu): `sudo apt install libportaudio2 xclip gir1.2-ayatanaappindicator3-0.1`
- GNOME needs the *AppIndicator* extension to show the tray icon.
- Terminals paste with Ctrl+Shift+V, so dictation into a terminal won't paste; other apps work.

CPU-only speed: expect ~3–8 s per dictation with `large-v3-turbo`. Set `"faster_whisper_model": "small"`
in `~/.localflow.json` for ~1.5 s at lower accuracy.

## Config

Optional `~/.localflow.json` overrides any field in `localflow/config.py`, e.g.:

```json
{ "hotkey": "cmd_r", "vocabulary": ["Kubernetes", "Altaf", "Taikisha"], "faster_whisper_model": "large-v3" }
```

`vocabulary` is appended to the Whisper prompt to bias recognition of names and jargon.

## Eval

```sh
uv run python eval/run_eval.py              # ASR + cleanup
uv run python eval/run_eval.py --no-cleanup # ASR only
```

Add your own recordings to `eval/clips/<id>.wav` with the expected Roman-Hinglish text in
`eval/references.tsv`. The bundled clips are synthetic (macOS "Lekha" voice) — real voice samples
are a much better benchmark.
