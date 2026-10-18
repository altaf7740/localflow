import io
import json
import threading
import urllib.error
import urllib.request
import wave
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from localflow.core.config.settings import Config
from scripts import web


def _wav(samples=np.full(16000, 1000), rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(np.asarray(samples, dtype=np.int16).tobytes())
    return buf.getvalue()


@pytest.fixture
def fake_models(monkeypatch):
    seen = {}

    def transcribe(audio, cfg):
        seen["audio"] = audio
        return "मैं कल"

    monkeypatch.setattr(web.asr, "transcribe", transcribe)
    monkeypatch.setattr(web.cleanup, "clean", lambda text, cfg: f"clean({text})")
    return seen


@pytest.fixture
def server(fake_models):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(Config()))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture
def start_server(fake_models):
    servers = []

    def start(**kwargs) -> str:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), web.make_handler(Config(), **kwargs))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        servers.append(httpd)
        return f"http://127.0.0.1:{httpd.server_port}"

    yield start
    for httpd in servers:
        httpd.shutdown()


def _post(url: str, body: bytes, headers: dict | None = None) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
        ) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_transcribe_runs_asr_then_cleanup(fake_models):
    out = web.transcribe(_wav(), Config())
    assert (out["raw"], out["text"]) == ("मैं कल", "clean(मैं कल)")
    assert fake_models["audio"].dtype == np.float32 and len(fake_models["audio"]) == 16000


def test_transcribe_can_skip_cleanup(fake_models):
    assert web.transcribe(_wav(), Config(), use_cleanup=False)["text"] == "मैं कल"


def test_transcribe_rejects_wrong_sample_rate(fake_models):
    with pytest.raises(ValueError, match="16 kHz"):
        web.transcribe(_wav(rate=44100), Config())


def test_http_transcribe(server):
    assert _post(f"{server}/api/transcribe", _wav())[1]["text"] == "clean(मैं कल)"
    assert _post(f"{server}/api/transcribe?cleanup=0", _wav())[1]["text"] == "मैं कल"


def test_http_transcribe_bad_audio_is_a_400(server):
    assert _post(f"{server}/api/transcribe", b"not a wav")[0] == 400
    assert _post(f"{server}/api/transcribe", b"")[0] == 400


def test_http_clean(server):
    assert _post(f"{server}/api/clean", json.dumps({"text": "hello"}).encode())[1]["text"] == "clean(hello)"
    assert _post(f"{server}/api/clean", b"[]")[0] == 400
    assert _post(f"{server}/api/clean", b"{}")[0] == 400


def test_http_serves_the_page(server):
    with urllib.request.urlopen(server) as resp:
        assert b"<title>LocalFlow</title>" in resp.read()


def test_http_api_key_is_required_when_set(start_server):
    url = start_server(api_key="s3cret") + "/api/transcribe"
    assert _post(url, _wav())[0] == 401
    assert _post(url, _wav(), {"Authorization": "Bearer wrong"})[0] == 401
    assert _post(url, _wav(), {"Authorization": "Bearer s3cret"})[1]["text"] == "clean(मैं कल)"


def test_http_cors_allows_only_listed_origins(start_server):
    url = start_server(cors=("https://app.example",)) + "/api/clean"
    body = json.dumps({"text": "hi"}).encode()

    def allowed(origin):
        req = urllib.request.Request(url, data=body, headers={"Origin": origin}, method="POST")
        with urllib.request.urlopen(req) as resp:
            return resp.headers.get("Access-Control-Allow-Origin")

    assert allowed("https://app.example") == "https://app.example"
    assert allowed("https://evil.example") is None
    with urllib.request.urlopen(
        urllib.request.Request(url, method="OPTIONS", headers={"Origin": "https://app.example"})
    ) as resp:
        assert resp.status == 204
        assert "Authorization" in resp.headers["Access-Control-Allow-Headers"]


def test_listening_beyond_localhost_needs_an_api_key(monkeypatch):
    monkeypatch.delenv(web.API_KEY_ENV, raising=False)
    monkeypatch.setattr("sys.argv", ["web", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as exit:
        web.main()
    assert exit.value.code == 1


def test_is_loopback():
    assert web.is_loopback("127.0.0.1") and web.is_loopback("localhost") and web.is_loopback("::1")
    assert not web.is_loopback("0.0.0.0") and not web.is_loopback("192.168.1.5")
