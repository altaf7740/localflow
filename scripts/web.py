"""Dictate over HTTP: send audio, get the cleaned-up Hinglish text back. Also serves a test page.

Usage: make web [HOST=0.0.0.0] [PORT=8766] [CORS=https://app.example.com]   (then open http://localhost:8766)
   or: uv run python -m scripts.web [--host 127.0.0.1] [--port 8766] [--cors ORIGIN ...]

API:
  POST /api/transcribe[?cleanup=0]  body: 16 kHz mono 16-bit WAV
       → {"raw": …, "text": …, "timings": {"asr": s, "llm": s}}
  POST /api/clean  body: {"text": "…"}
       → {"text": …, "timings": {"llm": s}}

  curl --data-binary @clip.wav http://localhost:8766/api/transcribe

Listens on localhost only by default. To accept other computers, set an API key and a host:
  export LOCALFLOW_API_KEY=$(openssl rand -hex 24)
  make web HOST=0.0.0.0
Callers then send `Authorization: Bearer <key>`.
"""

import argparse
import hmac
import io
import ipaddress
import json
import os
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from localflow.core.config.settings import Config
from localflow.modules.asr import services as asr
from localflow.modules.cleanup import services as cleanup
from localflow.shared.audio import load_wav

PAGE = Path(__file__).with_name("web.html")
MAX_AUDIO_BYTES = 20 * 2**20  # ~10 minutes of 16 kHz 16-bit mono
MAX_TEXT = 5000  # characters per /api/clean request
API_KEY_ENV = "LOCALFLOW_API_KEY"  # an env var, not a flag, so the key doesn't show up in `ps`

# one transcription at a time: there's a single loaded Whisper model
_asr_lock = threading.Lock()


def transcribe(wav: bytes, cfg: Config, use_cleanup: bool = True) -> dict:
    """Whisper, then (optionally) the Ollama cleanup, as in a hotkey dictation."""
    audio = load_wav(io.BytesIO(wav))
    with _asr_lock:
        t0 = time.time()
        raw = asr.transcribe(audio, cfg)
    t1 = time.time()
    text = cleanup.clean(raw, cfg) if use_cleanup else raw
    t2 = time.time()
    print(f"[web] [asr {t1 - t0:.2f}s] {raw}\n[web] [llm {t2 - t1:.2f}s] {text}", flush=True)
    return {"raw": raw, "text": text, "timings": {"asr": round(t1 - t0, 3), "llm": round(t2 - t1, 3)}}


def clean(text: str, cfg: Config) -> dict:
    t0 = time.time()
    out = cleanup.clean(text[:MAX_TEXT], cfg)
    return {"text": out, "timings": {"llm": round(time.time() - t0, 3)}}


def warmup(cfg: Config):
    """Load Whisper and the cleanup model at startup, so the first request doesn't wait for them.
    Requests that arrive meanwhile queue on the lock instead of loading Whisper a second time."""
    t0 = time.time()
    with _asr_lock:
        asr.warmup(cfg)
    cleanup.clean("hello", cfg)
    print(f"[web] ready in {time.time() - t0:.1f}s", flush=True)


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def make_handler(cfg: Config, api_key: str = "", cors: tuple[str, ...] = ()):
    """`api_key`: required as `Authorization: Bearer <key>` on /api/* when set.
    `cors`: browser origins (or "*") allowed to call the API from their own pages."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_OPTIONS(self):
            # CORS preflight: browsers send it before a cross-origin POST with JSON or Authorization
            self.send_response(204)
            self._cors_headers()
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self):
            url = urlsplit(self.path)
            if not self._authorized():
                return self._json({"error": "missing or wrong API key (Authorization: Bearer <key>)"}, 401)
            try:
                length = int(self.headers.get("Content-Length", 0))
            except ValueError:
                return self._json({"error": "bad Content-Length"}, 400)
            if length > MAX_AUDIO_BYTES:
                return self._json({"error": f"body over {MAX_AUDIO_BYTES // 2**20} MB"}, 413)
            body = self.rfile.read(length)
            if url.path == "/api/transcribe":
                if not body:
                    return self._json({"error": "no audio"}, 400)
                use_cleanup = parse_qs(url.query).get("cleanup", ["1"])[0] not in ("0", "false")
                try:
                    self._json(transcribe(body, cfg, use_cleanup))
                except (wave.Error, ValueError, EOFError) as e:  # not a WAV, or the wrong format
                    self._json({"error": str(e)}, 400)
            elif url.path == "/api/clean":
                try:
                    text = str(json.loads(body or b"{}").get("text", "")).strip()
                except (ValueError, AttributeError) as e:
                    return self._json({"error": f"bad request: {e}"}, 400)
                if not text:
                    return self._json({"error": "no text"}, 400)
                self._json(clean(text, cfg))
            else:
                self._send(404, b"not found", "text/plain")

        def _authorized(self) -> bool:
            if not api_key:
                return True
            sent = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            return hmac.compare_digest(sent.encode(), api_key.encode())

        def _cors_headers(self):
            origin = self.headers.get("Origin")
            if "*" in cors:
                self.send_header("Access-Control-Allow-Origin", "*")
            elif origin in cors:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def _json(self, data: dict, status: int = 200):
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass  # transcribe() prints its own [web] lines

    return Handler


def main():
    parser = argparse.ArgumentParser(prog="web", description="LocalFlow dictation over HTTP, with a test page.")
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to accept other computers (needs an API key)")
    # 8765 is LocalVoice's test page, so both can run at once
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--cors", nargs="*", default=[], metavar="ORIGIN", help='browser origins allowed, or "*"')
    args = parser.parse_args()
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not is_loopback(args.host) and not api_key:
        parser.exit(
            1,
            f"--host {args.host} lets other computers in, so it needs an API key:\n"
            f"  export {API_KEY_ENV}=$(openssl rand -hex 24)\n",
        )
    cfg = Config.load()
    try:
        server = ThreadingHTTPServer((args.host, args.port), make_handler(cfg, api_key, tuple(args.cors)))
    except OSError as e:
        parser.exit(1, f"can't listen on {args.host}:{args.port} ({e.strerror}): is it already running? Try --port\n")
    where = "localhost only" if is_loopback(args.host) else f"{args.host}, API key required"
    print(f"LocalFlow HTTP on http://localhost:{args.port} ({where}; Ctrl+C to quit)", flush=True)
    threading.Thread(target=warmup, args=(cfg,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
