import numpy as np

from src.core.config.settings import Config
from src.modules.asr import services


def _fail(*args, **kwargs):
    raise AssertionError("model should not be called")


def test_short_tap_is_ignored_without_loading_model(monkeypatch):
    monkeypatch.setattr(services, "_transcribe_mlx", _fail)
    monkeypatch.setattr(services, "_transcribe_faster_whisper", _fail)
    assert services.transcribe(np.full(1000, 0.5, dtype=np.float32), Config()) == ""


def test_silence_is_ignored_without_loading_model(monkeypatch):
    monkeypatch.setattr(services, "_transcribe_mlx", _fail)
    monkeypatch.setattr(services, "_transcribe_faster_whisper", _fail)
    assert services.transcribe(np.zeros(32000, dtype=np.float32), Config()) == ""


def test_vocabulary_is_appended_to_prompt(monkeypatch):
    seen = {}
    monkeypatch.setattr(services, "_use_mlx", lambda cfg: True)
    monkeypatch.setattr(services, "_transcribe_mlx", lambda audio, prompt, cfg: seen.setdefault("prompt", prompt))
    services.transcribe(np.full(32000, 0.5, dtype=np.float32), Config(vocabulary=["Kubernetes", "Altaf"]))
    assert seen["prompt"].endswith("Kubernetes, Altaf.")


def test_auto_backend_follows_platform(monkeypatch):
    monkeypatch.setattr(services, "APPLE_SILICON", False)
    assert services._use_mlx(Config(asr_backend="auto")) is False
    assert services._use_mlx(Config(asr_backend="mlx")) is True
