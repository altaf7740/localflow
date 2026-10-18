import threading

import numpy as np
import sounddevice as sd
from pynput import keyboard

from localflow.core import dictation
from localflow.core.config.settings import Config
from localflow.core.dictation import IDLE, RECORDING, Dictation


class FakeRecorder:
    audio = np.full(16000, 0.1, dtype=np.float32)
    fail = False

    def start(self, device=""):
        if self.fail:
            raise sd.PortAudioError("device unavailable")
        return device or "Default Mic"

    def stop(self):
        return self.audio


def _make(monkeypatch, recorder=None):
    states, processed, dead = [], [], []
    monkeypatch.setattr(dictation, "Recorder", recorder or FakeRecorder)
    d = Dictation(Config(hotkey="alt_l"), states.append, lambda text: None, dead.append)
    monkeypatch.setattr(d, "_process", processed.append)
    return d, states, processed, dead


def _join_workers():
    for t in threading.enumerate():
        if t is not threading.current_thread() and t.daemon:
            t.join(timeout=1)


def test_hold_and_release_processes_audio(monkeypatch):
    d, states, processed, dead = _make(monkeypatch)
    d._on_press(keyboard.Key.alt_l)
    d._on_release(keyboard.Key.alt_l)
    _join_workers()
    assert states == [RECORDING]
    assert len(processed) == 1
    assert dead == []


def test_hotkey_used_as_modifier_cancels_recording(monkeypatch):
    d, states, processed, dead = _make(monkeypatch)
    d._on_press(keyboard.Key.alt_l)
    d._on_press(keyboard.Key.left)  # ⌥← word jump
    d._on_release(keyboard.Key.left)
    d._on_release(keyboard.Key.alt_l)
    _join_workers()
    assert states == [RECORDING, IDLE]
    assert processed == []


def test_all_zero_recording_reports_dead_mic(monkeypatch):
    class LidClosedRecorder(FakeRecorder):
        audio = np.zeros(16000, dtype=np.float32)

    d, states, processed, dead = _make(monkeypatch, LidClosedRecorder)
    d._on_press(keyboard.Key.alt_l)
    d._on_release(keyboard.Key.alt_l)
    _join_workers()
    assert dead == ["Default Mic"]
    assert processed == []
    assert states == [RECORDING, IDLE]


def test_mic_that_fails_to_open_reports_dead_mic(monkeypatch):
    class BrokenRecorder(FakeRecorder):
        fail = True

    d, states, processed, dead = _make(monkeypatch, BrokenRecorder)
    d._on_press(keyboard.Key.alt_l)
    d._on_release(keyboard.Key.alt_l)
    assert dead == ["system default"]
    assert states == []
    assert processed == []
