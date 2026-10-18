import re

import requests

from ...core.config.settings import Config
from .prompt import EXAMPLES, SYSTEM_PROMPT, TRANSLITERATE_PROMPT

DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def clean(text: str, cfg: Config) -> str:
    if not text or not cfg.cleanup_enabled:
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
