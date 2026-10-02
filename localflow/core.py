import threading
import time
from typing import Callable

from pynput import keyboard

from . import asr, cleanup
from .audio import Recorder
from .config import Config
from .paste import paste_text

LOADING, IDLE, RECORDING, WORKING = "loading", "idle", "recording", "working"


class Dictation:
    """Hold-to-talk loop shared by every UI. The UI only renders state changes."""

    def __init__(self, cfg: Config, on_state: Callable[[str], None], on_result: Callable[[str], None]):
        self.cfg = cfg
        self.on_state = on_state
        self.on_result = on_result
        self.recorder = Recorder()
        self.hotkey = getattr(keyboard.Key, cfg.hotkey)
        self.recording = False
        self.busy = threading.Lock()

    def start(self):
        self.on_state(LOADING)
        threading.Thread(target=self._warmup, daemon=True).start()
        keyboard.Listener(on_press=self._on_press, on_release=self._on_release).start()

    def _warmup(self):
        asr.warmup(self.cfg)
        cleanup.clean("hello", self.cfg)
        self.on_state(IDLE)

    def _on_press(self, key):
        if key == self.hotkey and not self.recording and not self.busy.locked():
            self.recording = True
            self.on_state(RECORDING)
            self.recorder.start()

    def _on_release(self, key):
        if key == self.hotkey and self.recording:
            self.recording = False
            audio = self.recorder.stop()
            threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio):
        with self.busy:
            self.on_state(WORKING)
            t0 = time.time()
            raw = asr.transcribe(audio, self.cfg)
            t1 = time.time()
            text = cleanup.clean(raw, self.cfg)
            t2 = time.time()
            print(f"[asr {t1 - t0:.2f}s] {raw}\n[llm {t2 - t1:.2f}s] {text}", flush=True)
            if text:
                paste_text(text + " ")
                self.on_result(text)
            self.on_state(IDLE)
