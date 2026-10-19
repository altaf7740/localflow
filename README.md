# LocalFlow

Fully local, Wispr Flow–style dictation for macOS, Windows and Linux that handles Hinglish.
Hold the hotkey (**Left ⌥** on macOS, **Right Ctrl** on Windows/Linux), speak, release — cleaned-up text (Hindi in Roman script) is pasted into the focused app.

For the other direction — select Hinglish text and hear it read aloud — see
[LocalVoice](https://github.com/altaf7740/localvoice). The two use different hotkeys and can run at the same time;
`make stop` / `make status` in each repo only touch that repo's app.

## Pipeline

1. **Record**: `sounddevice`, 16 kHz mono, while the hotkey is held.
2. **ASR**
   - **Apple Silicon:** [Whisper-Hindi2Hinglish-Apex](https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Apex)
     on MLX. It's a large-v3-turbo fine-tune that writes Hindi in Roman script itself, so no transliteration pass is needed.
   - **Elsewhere:** Whisper large-v3-turbo via faster-whisper (CUDA if available, else CPU int8), with
     `language="hi"`, which outputs Devanagari + English.
3. **Cleanup**
   - **Rules, every platform, no model:**
     - Drop "um", "uh" and "hmm".
     - Resolve self-corrections:
       - "kal nahin parso" → "parso".
       - "Rahul ko call karo, actually Amit ko call karo" → "Amit ko call karo": the replacement echoes the
         words it replaces, and they're swapped.
     - Anything that doesn't line up is left as spoken, so negations ("main nahi aaunga", "aaj nahi to kal")
       and "…, actually …" used as "by the way" stay intact.
   - **Windows/Linux only:** `qwen2.5:7b-instruct` via Ollama transliterates stock Whisper's Devanagari to Roman
     Hinglish. If Ollama is down, the raw transcript is pasted.

   On the bundled eval clips (M2 Pro), Apex + rules scored WER 0.048 at 0.63 s/clip, versus 0.055 at
   1.27 s/clip for stock turbo + LLM.
4. **Paste**: clipboard + ⌘V / Ctrl+V, then the previous clipboard is restored.

Nothing leaves the machine.

## Setup

| | macOS (Apple Silicon) | Windows | Linux |
|---|---|---|---|
| ASR | Hinglish Whisper, MLX (GPU) | faster-whisper (CUDA or CPU) | faster-whisper (CUDA or CPU) |
| Cleanup LLM | none | Ollama | Ollama |
| UI | menu bar | system tray | system tray |
| Hotkey | Left ⌥ | Right Ctrl | Right Ctrl |

Install [uv](https://docs.astral.sh/uv/) (plus [Ollama](https://ollama.com) on Windows/Linux), then

```sh
make install   # uv sync --all-groups
make model     # Apple Silicon: convert Hinglish Whisper to MLX; else: ollama pull qwen2.5:7b-instruct
make start
```

Run `make` to list every target.

### HTTP

`make web` runs the same pipeline as an HTTP server on http://localhost:8766 (`PORT=…` to change;
LocalVoice's test page uses 8765). Open it in a browser to record from the mic or upload audio in
any format, or call it directly:

```sh
curl --data-binary @clip.wav localhost:8766/api/transcribe            # 16 kHz mono 16-bit WAV
curl --data-binary @clip.wav 'localhost:8766/api/transcribe?cleanup=0'  # Whisper only
curl -d '{"text": "मैं कल meeting में आऊंगा"}' localhost:8766/api/clean   # cleanup only
```

`/api/transcribe` returns `{"raw", "text", "timings": {"asr", "llm"}}`. It loads its own copy of
Whisper, separate from `make start`.

By default it listens on localhost only. To accept other computers, set an API key (it refuses to
start without one) and listen on all interfaces:

```sh
export LOCALFLOW_API_KEY=$(openssl rand -hex 24)
make web HOST=0.0.0.0
# from another machine:
curl -H "Authorization: Bearer $LOCALFLOW_API_KEY" --data-binary @clip.wav http://<this-mac's-ip>:8766/api/transcribe
```

macOS asks once whether to allow incoming connections for Python; allow it. Browser pages on other
origins also need CORS: `make web HOST=0.0.0.0 CORS="https://app.example.com"` (or `CORS="*"`).
Traffic is plain HTTP, so keep it to a trusted network; across the internet, use a tunnel such as
Tailscale or Cloudflare Tunnel instead of forwarding a router port.

### macOS (Apple Silicon)

`make model` downloads Oriserve/Whisper-Hindi2Hinglish-Apex (~1.6 GB) and converts it into
`localflow/static/models/`. To go back to stock Whisper, set `asr_model` to
`"mlx-community/whisper-large-v3-turbo"` and `asr_language` to `"hi"`.

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

Optional `~/.localflow.json` overrides any field in `localflow/core/config/settings.py`, e.g.:

```json
{ "hotkey": "cmd_r", "vocabulary": ["Kubernetes", "Altaf", "Taikisha"], "faster_whisper_model": "large-v3" }
```

`vocabulary` is appended to the Whisper prompt to bias recognition of names and jargon.

### Microphone

Pick the input device from the **Microphone** menu (menu bar / tray); the choice is saved as
`input_device`. If the chosen mic is unplugged, LocalFlow falls back to the system default.

When a recording is pure digital silence — MacBook lid closed, mic muted or disconnected —
LocalFlow doesn't transcribe it. On macOS a dialog offers to switch to another mic; on
Windows/Linux a tray notification asks you to pick one.

## Eval

```sh
make eval                                          # configured pipeline: WER, median latency, peak memory
make eval ARGS="--asr path/to/other-mlx-model:en"  # compare another MLX Whisper (repeatable)
make eval ARGS="--llm qwen2.5:7b-instruct"         # also run it with LLM cleanup
```

Add your own recordings to `localflow/static/eval/clips/<id>.wav` (16 kHz mono) with the expected
Roman-Hinglish text in `localflow/static/eval/references.tsv`. The bundled clips are synthetic
(macOS "Lekha" voice) and fluent. Real voice samples, including fillers and self-corrections
("kal, nahi, parso"), are a much better benchmark.

## Development

```sh
make test       # pytest (localflow/tests)
make lint-fix   # ruff check --fix + ruff format
make check      # lint-fix + test
```

## Project structure

```
├── makefile
├── pyproject.toml
├── scripts/
│   ├── convert_hf_whisper.py   # HF Whisper → MLX weights (`make model`)
│   ├── run_eval.py             # WER + latency benchmark (`make eval`)
│   └── web.py, web.html        # HTTP API + test page (`make web`)
└── localflow/
    ├── main.py                 # entry point: menu bar (macOS) or tray (Windows/Linux)
    ├── core/
    │   ├── config/settings.py  # Config + ~/.localflow.json overrides
    │   └── dictation.py        # hold-to-talk loop shared by every UI
    ├── shared/
    │   ├── audio.py            # mic recorder, WAV loading
    │   └── paste.py            # clipboard + ⌘V / Ctrl+V
    ├── modules/
    │   ├── asr/                # Whisper: MLX or faster-whisper
    │   ├── cleanup/            # Ollama cleanup + prompts
    │   ├── evaluation/         # WER metrics
    │   └── ui/                 # menubar.py (rumps), tray.py (pystray)
    ├── static/
    │   ├── models/             # converted Whisper weights (gitignored)
    │   └── eval/               # benchmark clips + references
    └── tests/
```
