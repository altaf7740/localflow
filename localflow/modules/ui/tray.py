"""System-tray UI for Windows and Linux."""

import threading
import time

import pystray
from PIL import Image, ImageDraw

from ...core.config.settings import Config
from ...core.dictation import IDLE, LOADING, RECORDING, WORKING, Dictation

COLORS = {LOADING: "#9e9e9e", IDLE: "#2e7d32", RECORDING: "#d32f2f", WORKING: "#f9a825"}
TOOLTIPS = {
    LOADING: "LocalFlow: loading models…",
    IDLE: "LocalFlow: ready",
    RECORDING: "LocalFlow: listening",
    WORKING: "LocalFlow: transcribing",
}


def _dot(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=color)
    return img


ICONS = {state: _dot(color) for state, color in COLORS.items()}


def run(cfg: Config):
    last = {"text": "—"}

    def set_state(state: str):
        icon.icon = ICONS[state]
        icon.title = TOOLTIPS[state]

    def set_last(text: str):
        last["text"] = text[:60]
        icon.update_menu()

    def on_dead_mic(device: str):
        icon.notify(
            f"No audio from {device}. Is it muted or unplugged? Pick another mic from the LocalFlow tray menu.",
            "LocalFlow",
        )

    def toggle_cleanup(_icon, _item):
        cfg.cleanup_enabled = not cfg.cleanup_enabled

    def set_mic(name: str):
        def choose(_icon, _item):
            cfg.input_device = name
            cfg.save("input_device")
            icon.update_menu()

        return choose

    def mic_items():
        devices = dictation.recorder.input_devices()
        default_name = dictation.recorder.default_device()
        yield pystray.MenuItem(
            f"System default ({default_name})",
            set_mic(""),
            checked=lambda _: not cfg.input_device or cfg.input_device not in devices,
            radio=True,
        )
        for name in devices:
            yield pystray.MenuItem(name, set_mic(name), checked=lambda _, n=name: cfg.input_device == n, radio=True)

    dictation = Dictation(cfg, set_state, set_last, on_dead_mic)
    icon = pystray.Icon(
        "LocalFlow",
        ICONS[LOADING],
        TOOLTIPS[LOADING],
        menu=pystray.Menu(
            pystray.MenuItem("AI cleanup", toggle_cleanup, checked=lambda _: cfg.cleanup_enabled),
            pystray.MenuItem("Microphone", pystray.Menu(mic_items)),
            pystray.MenuItem(lambda _: f"Last: {last['text']}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda i, _: i.stop()),
        ),
    )

    def watch_mics():
        # backends only rebuild the native menu on update_menu(), so poll for plugged/unplugged mics
        seen = None
        while True:
            current = (dictation.recorder.input_devices(), dictation.recorder.default_device())
            if current != seen:
                seen = current
                icon.update_menu()
            time.sleep(3)

    def setup(i: pystray.Icon):
        i.visible = True
        dictation.start()
        threading.Thread(target=watch_mics, daemon=True).start()

    icon.run(setup=setup)
