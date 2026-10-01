import threading
import time

import rumps
from pynput import keyboard

from . import asr, cleanup
from .audio import Recorder
from .config import Config
from .paste import paste_text

IDLE, RECORDING, WORKING = "🎙", "🔴", "⏳"


class LocalFlowApp(rumps.App):
    def __init__(self):
        super().__init__("LocalFlow", title="…", quit_button="Quit")
        self.cfg = Config.load()
        self.recorder = Recorder()
        self.hotkey = getattr(keyboard.Key, self.cfg.hotkey)
        self.recording = False
        self.busy = threading.Lock()
        self.cleanup_item = rumps.MenuItem("AI cleanup", callback=self.toggle_cleanup)
        self.cleanup_item.state = self.cfg.cleanup_enabled
        self.last_item = rumps.MenuItem("Last: —")
        self.menu = [self.cleanup_item, self.last_item, None]
        threading.Thread(target=self._warmup, daemon=True).start()
        keyboard.Listener(on_press=self._on_press, on_release=self._on_release).start()

    def _warmup(self):
        asr.warmup(self.cfg)
        cleanup.clean("hello", self.cfg)
        self.title = IDLE

    def toggle_cleanup(self, item):
        item.state = not item.state
        self.cfg.cleanup_enabled = bool(item.state)

    def _on_press(self, key):
        if key == self.hotkey and not self.recording and not self.busy.locked():
            self.recording = True
            self.title = RECORDING
            self.recorder.start()

    def _on_release(self, key):
        if key == self.hotkey and self.recording:
            self.recording = False
            audio = self.recorder.stop()
            threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio):
        with self.busy:
            self.title = WORKING
            t0 = time.time()
            raw = asr.transcribe(audio, self.cfg)
            t1 = time.time()
            text = cleanup.clean(raw, self.cfg)
            t2 = time.time()
            print(f"[asr {t1 - t0:.2f}s] {raw}\n[llm {t2 - t1:.2f}s] {text}", flush=True)
            if text:
                paste_text(text + " ")
                self.last_item.title = f"Last: {text[:60]}"
            self.title = IDLE


def main():
    LocalFlowApp().run()


if __name__ == "__main__":
    main()
