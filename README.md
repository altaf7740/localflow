# LocalFlow

Fully local, Wispr Flow–style dictation for macOS (Apple Silicon) that handles Hinglish.
Hold **Right ⌥**, speak, release — cleaned-up text (Hindi in Roman script) is pasted into the focused app.

## Pipeline

1. **Record** — `sounddevice`, 16 kHz mono, while the hotkey is held.
2. **ASR** — Whisper large-v3-turbo on MLX, `language="hi"`. This recognises Hindi words most
   accurately (output is Devanagari + English).
3. **Cleanup** — `qwen2.5:7b-instruct` via Ollama: transliterates to Roman Hinglish, removes fillers,
   fixes punctuation. Leftover Devanagari triggers a narrow transliteration pass. If Ollama is down
   the raw transcript is pasted.
4. **Paste** — clipboard + ⌘V, then the previous clipboard is restored.

Nothing leaves the machine.

## Setup

```sh
uv sync
# Whisper: convert the HF checkpoint to MLX (or set asr_model to "mlx-community/whisper-large-v3-turbo")
uv run python scripts/convert_hf_whisper.py openai/whisper-large-v3-turbo models/whisper-large-v3-turbo-mlx
ollama pull qwen2.5:7b-instruct
uv run localflow
```

Grant your terminal **Microphone**, **Accessibility** and **Input Monitoring** in
System Settings → Privacy & Security (needed to record, listen for the hotkey and paste).

## Config

Optional `~/.localflow.json` overrides any field in `localflow/config.py`, e.g.:

```json
{ "hotkey": "cmd_r", "vocabulary": ["Kubernetes", "Altaf", "Taikisha"], "cleanup_model": "qwen2.5:7b-instruct" }
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
