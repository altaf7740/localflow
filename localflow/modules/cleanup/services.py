import re

import requests

from ...core.config.settings import Config
from . import model, rules
from .prompt import EXAMPLES, SYSTEM_PROMPT, TRANSLITERATE_PROMPT

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def clean(text: str, cfg: Config) -> str:
    if not text:
        return text
    if not DEVANAGARI.search(text) and model.available(cfg):
        out = model.clean(text, cfg)
        if out is not None:
            return out[:1].upper() + out[1:]
    text = rules.clean(text)
    # the LLM is only needed to transliterate stock Whisper's Devanagari; Roman text is done
    if not cfg.cleanup_enabled or not DEVANAGARI.search(text):
        return text
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for raw, fixed in EXAMPLES:
        messages += [{"role": "user", "content": _wrap(raw)}, {"role": "assistant", "content": fixed}]
    messages.append({"role": "user", "content": _wrap(text)})
    out = _chat(messages, cfg) or text
    if DEVANAGARI.search(out):
        # the cleanup model sometimes copies Devanagari through; a narrow second pass fixes it
        retry = [{"role": "system", "content": TRANSLITERATE_PROMPT}, {"role": "user", "content": out}]
        out = _chat(retry, cfg) or out
    return out


def warmup(cfg: Config):
    """Load the cleanup models now, so the first dictation doesn't wait for them."""
    model.warmup(cfg)
    if cfg.cleanup_enabled:
        _chat([{"role": "user", "content": "hi"}], cfg)


def _wrap(text: str) -> str:
    return f"<transcript>{text}</transcript>"


def _chat(messages: list[dict], cfg: Config) -> str:
    try:
        resp = requests.post(
            f"{cfg.ollama_url}/api/chat",
            json={
                "model": cfg.cleanup_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "30m",
                "options": {"temperature": 0},
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.RequestException:
        return ""  # caller falls back to the raw text so dictation is never lost
