"""Task-specific cleanup model: a small LLM fine-tuned only to resolve fillers, stutters and
self-corrections in Roman Hinglish (see training/). Runs on MLX, so Apple Silicon only."""

import re
from pathlib import Path

from ...core.config.settings import Config
from ..evaluation.metrics import normalize

# only text that could need cleaning goes to the model; a fluent sentence is returned untouched,
# so the model never gets the chance to drop a word from it
NEEDS_MODEL = re.compile(
    r"\b(?:nahi+n?|nai|no|sorry|I mean|actually|wait|u+m+|u+h+|h+m+|you know|basically)\b|\b(\w+) \1\b",
    re.IGNORECASE,
)

_loaded = None  # (path, model, tokenizer)


def available(cfg: Config) -> bool:
    return bool(cfg.cleanup_model_path) and (Path(cfg.cleanup_model_path) / "config.json").exists()


def clean(text: str, cfg: Config) -> str | None:
    """The model's cleanup of `text`, or None when it isn't needed or can't be trusted."""
    if not NEEDS_MODEL.search(text):
        return None
    model, tokenizer = _load(cfg.cleanup_model_path)
    from mlx_lm import generate

    prompt = tokenizer.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True)
    out = generate(model, tokenizer, prompt, max_tokens=len(tokenizer.encode(text)) + 16).strip()
    return out if out and not adds_words(text, out) else None


def warmup(cfg: Config):
    if available(cfg):
        clean("main main kal aaunga", cfg)


def adds_words(before: str, after: str) -> bool:
    """Cleanup only drops or moves the speaker's words; a new word means the model made something up."""
    said = set(normalize(before))
    return any(w not in said for w in normalize(after))


def _load(path: str):
    global _loaded
    if _loaded is None or _loaded[0] != path:
        from mlx_lm import load

        model, tokenizer = load(path)
        _loaded = (path, model, tokenizer)
    return _loaded[1], _loaded[2]
