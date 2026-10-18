import threading
import time
from typing import Callable

import sounddevice as sd
from pynput import keyboard

from ..modules.asr import services as asr
from ..modules.cleanup import services as cleanup
from ..shared.audio import Recorder, is_dead_mic
from ..shared.paste import paste_text
from .config.settings import Config

LOADING, IDLE, RECORDING, WORKING = "loading", "idle", "recording", "working"


class Dictation:
    """Hold-to-talk loop shared by every UI. The UI only renders state changes."""

    def __init__(
        self,
        cfg: Config,
        on_state: Callable[[str], None],
        on_result: Callable[[str], None],
        on_dead_mic: Callable[[str], None],
    ):
        self.cfg = cfg
        self.on_state = on_state
        self.on_result = on_result
        self.on_dead_mic = on_dead_mic  # called with the device name when a mic gives no audio
        self.recorder = Recorder()
        self.hotkey = getattr(keyboard.Key, cfg.hotkey)
        self.recording = False
        self.device = ""
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
            try:
                self.device = self.recorder.start(self.cfg.input_device)
            except sd.PortAudioError:
                self.on_dead_mic(self.cfg.input_device or "system default")
                return
            self.recording = True
            self.on_state(RECORDING)
        elif key != self.hotkey and self.recording:
            # hotkey used as a modifier (e.g. ⌥← word jump): drop the recording
            self.recording = False
            self.recorder.stop()
            self.on_state(IDLE)

    def _on_release(self, key):
        if key == self.hotkey and self.recording:
            self.recording = False
            audio = self.recorder.stop()
            if is_dead_mic(audio):
                self.on_state(IDLE)
                self.on_dead_mic(self.device)
                return
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
