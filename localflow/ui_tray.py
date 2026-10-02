"""System-tray UI for Windows and Linux."""
import pystray
from PIL import Image, ImageDraw

from .config import Config
from .core import IDLE, LOADING, RECORDING, WORKING, Dictation

COLORS = {LOADING: "#9e9e9e", IDLE: "#2e7d32", RECORDING: "#d32f2f", WORKING: "#f9a825"}
TOOLTIPS = {LOADING: "LocalFlow: loading models…", IDLE: "LocalFlow: ready",
            RECORDING: "LocalFlow: listening", WORKING: "LocalFlow: transcribing"}


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

    def toggle_cleanup(_icon, _item):
        cfg.cleanup_enabled = not cfg.cleanup_enabled

    icon = pystray.Icon(
        "LocalFlow",
        ICONS[LOADING],
        TOOLTIPS[LOADING],
        menu=pystray.Menu(
            pystray.MenuItem("AI cleanup", toggle_cleanup, checked=lambda _: cfg.cleanup_enabled),
            pystray.MenuItem(lambda _: f"Last: {last['text']}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda i, _: i.stop()),
        ),
    )

    def setup(i: pystray.Icon):
        i.visible = True
        Dictation(cfg, set_state, set_last).start()

    icon.run(setup=setup)
