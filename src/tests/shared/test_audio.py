import wave

import numpy as np
import pytest

from src.shared.audio import SAMPLE_RATE, load_wav


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
