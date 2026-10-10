import wave

import numpy as np
import pytest

from src.shared import audio
from src.shared.audio import SAMPLE_RATE, Recorder, is_dead_mic, load_wav


def _write_wav(path, samples: np.ndarray, rate=SAMPLE_RATE, channels=1):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(samples.astype(np.int16).tobytes())


def test_load_wav_scales_to_float(tmp_path):
    path = tmp_path / "a.wav"
    _write_wav(path, np.array([0, 16384, -32768]))
    audio = load_wav(str(path))
    assert audio.dtype == np.float32
    np.testing.assert_allclose(audio, [0.0, 0.5, -1.0])


def test_load_wav_rejects_wrong_sample_rate(tmp_path):
    path = tmp_path / "b.wav"
    _write_wav(path, np.zeros(10), rate=44100)
    with pytest.raises(ValueError, match="16 kHz"):
        load_wav(str(path))


def test_is_dead_mic_only_for_digital_silence():
    assert is_dead_mic(np.zeros(SAMPLE_RATE, dtype=np.float32))
    assert not is_dead_mic(np.full(SAMPLE_RATE, 1e-5, dtype=np.float32))  # quiet room still has a noise floor
    assert not is_dead_mic(np.zeros(100, dtype=np.float32))  # too short to judge


class _FakeStream:
    def __init__(self, device, **kwargs):
        self.device = device

    def start(self):
        pass


def test_recorder_falls_back_to_default_when_device_unplugged(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(rec, "_scan", lambda: ["MacBook Pro Microphone"])
    monkeypatch.setattr(rec, "default_device", lambda: "MacBook Pro Microphone")
    monkeypatch.setattr(audio.sd, "InputStream", _FakeStream)
    assert rec.start("AirPods Pro") == "MacBook Pro Microphone"
    rec._stream = None
    assert rec.start("") == "MacBook Pro Microphone"


def test_recorder_uses_chosen_device_when_present(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(rec, "_scan", lambda: ["MacBook Pro Microphone", "iPhone Microphone"])
    monkeypatch.setattr(audio.sd, "InputStream", _FakeStream)
    assert rec.start("iPhone Microphone") == "iPhone Microphone"
    assert rec._stream.device == "iPhone Microphone"
