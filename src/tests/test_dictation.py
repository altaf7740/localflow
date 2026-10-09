import numpy as np
from pynput import keyboard

from src.core import dictation
from src.core.config.settings import Config
from src.core.dictation import IDLE, RECORDING, Dictation


class FakeRecorder:
    def start(self):
        pass

    def stop(self):
        return np.zeros(0, dtype=np.float32)


def _make(monkeypatch):
    states, processed = [], []
    monkeypatch.setattr(dictation, "Recorder", FakeRecorder)
    d = Dictation(Config(hotkey="alt_l"), states.append, lambda text: None)
    monkeypatch.setattr(d, "_process", processed.append)
    return d, states, processed


def _join_workers():
    import threading

    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(timeout=1)


def test_hold_and_release_processes_audio(monkeypatch):
    d, states, processed = _make(monkeypatch)
    d._on_press(keyboard.Key.alt_l)
    d._on_release(keyboard.Key.alt_l)
    _join_workers()
    assert states == [RECORDING]
    assert len(processed) == 1


def test_hotkey_used_as_modifier_cancels_recording(monkeypatch):
    d, states, processed = _make(monkeypatch)
    d._on_press(keyboard.Key.alt_l)
    d._on_press(keyboard.Key.left)  # ⌥← word jump
    d._on_release(keyboard.Key.left)
    d._on_release(keyboard.Key.alt_l)
    _join_workers()
    assert states == [RECORDING, IDLE]
    assert processed == []
