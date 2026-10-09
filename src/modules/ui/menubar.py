import rumps

from ...core.config.settings import Config
from ...core.dictation import IDLE, LOADING, RECORDING, WORKING, Dictation

TITLES = {LOADING: "…", IDLE: "🎙", RECORDING: "🔴", WORKING: "⏳"}


class MenuBarApp(rumps.App):
    def __init__(self, cfg: Config):
        super().__init__("LocalFlow", title=TITLES[LOADING], quit_button="Quit")
        self.cfg = cfg
        self.cleanup_item = rumps.MenuItem("AI cleanup", callback=self.toggle_cleanup)
        self.cleanup_item.state = cfg.cleanup_enabled
        self.last_item = rumps.MenuItem("Last: —")
        self.menu = [self.cleanup_item, self.last_item, None]
        Dictation(cfg, self.set_state, self.set_last).start()

    def set_state(self, state: str):
        self.title = TITLES[state]

    def set_last(self, text: str):
        self.last_item.title = f"Last: {text[:60]}"

    def toggle_cleanup(self, item):
        item.state = not item.state
        self.cfg.cleanup_enabled = bool(item.state)


def run(cfg: Config):
    MenuBarApp(cfg).run()
