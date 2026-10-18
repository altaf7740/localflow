import threading
import wave
from typing import BinaryIO

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000


class Recorder:
    def __init__(self):
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def input_devices(self) -> list[str]:
        """Current input device names, re-scanned so mics plugged in after launch show up."""
        with self._lock:
            return self._scan()

    def default_device(self) -> str:
        return sd.query_devices(kind="input")["name"]

    def start(self, device: str = "") -> str:
        """Start recording from `device` (system default if empty or unplugged). Returns the device used."""
        with self._lock:
            if not device or device not in self._scan():
                device = self.default_device()
            self._chunks = []
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", device=device, callback=self._on_audio
            )
            self._stream.start()
        return device

    def _scan(self) -> list[str]:
        if self._stream is None:  # re-initialising PortAudio would kill an open stream
            sd._terminate()
            sd._initialize()
        return [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]

    def _on_audio(self, indata, frames, time, status):
        with self._lock:
            self._chunks.append(indata[:, 0].copy())

    def stop(self) -> np.ndarray:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self._chunks)


def is_dead_mic(audio: np.ndarray) -> bool:
    """True when a recording is digital silence: every real mic has a noise floor, so all-zero
    audio means the device delivers nothing (MacBook lid closed, muted or disconnected mic)."""
    return audio.size >= SAMPLE_RATE // 4 and not np.any(audio)


def load_wav(source: str | BinaryIO) -> np.ndarray:
    """Read a 16 kHz mono 16-bit WAV (a path or file object) as float32 in [-1, 1]."""
    with wave.open(source, "rb") as f:
        if (f.getframerate(), f.getnchannels(), f.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            name = source if isinstance(source, str) else "audio"
            raise ValueError(f"{name}: expected 16 kHz mono 16-bit WAV (convert with ffmpeg -ar 16000 -ac 1)")
        data = f.readframes(f.getnframes())
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
