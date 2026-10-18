import rumps
from PyObjCTools.AppHelper import callAfter

from ...core.config.settings import Config
from ...core.dictation import IDLE, LOADING, RECORDING, WORKING, Dictation

TITLES = {LOADING: "…", IDLE: "🎙", RECORDING: "🔴", WORKING: "⏳"}
SYSTEM_DEFAULT = "System default"


class MenuBarApp(rumps.App):
    def __init__(self, cfg: Config):
        super().__init__("LocalFlow", title=TITLES[LOADING], quit_button="Quit")
        self.cfg = cfg
        self.dictation = Dictation(cfg, self.set_state, self.set_last, self.on_dead_mic)
        self.cleanup_item = rumps.MenuItem("AI cleanup", callback=self.toggle_cleanup)
        self.cleanup_item.state = cfg.cleanup_enabled
        self.mic_menu = rumps.MenuItem("Microphone")
        self.last_item = rumps.MenuItem("Last: —")
        self.menu = [self.cleanup_item, self.mic_menu, self.last_item, None]
        self.devices: tuple[list[str], str] = ([], "")
        self.refresh_mics()
        # pick up mics that are plugged in / removed while the app runs
        rumps.Timer(lambda _: self.refresh_mics(), 3).start()
        self.dictation.start()

    def set_state(self, state: str):
        self.title = TITLES[state]

    def set_last(self, text: str):
        self.last_item.title = f"Last: {text[:60]}"

    def toggle_cleanup(self, item):
        item.state = not item.state
        self.cfg.cleanup_enabled = bool(item.state)

    def refresh_mics(self, force: bool = False):
        devices = self.dictation.recorder.input_devices()
        default_name = self.dictation.recorder.default_device()
        if (devices, default_name) == self.devices and not force:
            return
        self.devices = (devices, default_name)
        if len(self.mic_menu):  # clear() fails before the submenu exists
            self.mic_menu.clear()
        default = rumps.MenuItem(f"{SYSTEM_DEFAULT} ({default_name})", self.choose_mic)
        default.state = not self.cfg.input_device or self.cfg.input_device not in devices
        self.mic_menu.add(default)
        self.mic_menu.add(None)
        for name in devices:
            item = rumps.MenuItem(name, callback=self.choose_mic)
            item.state = name == self.cfg.input_device
            self.mic_menu.add(item)

    def choose_mic(self, item):
        self.set_mic("" if item.title.startswith(SYSTEM_DEFAULT) else item.title)

    def set_mic(self, name: str):
        self.cfg.input_device = name
        self.cfg.save("input_device")
        self.refresh_mics(force=True)

    def on_dead_mic(self, device: str):
        callAfter(self._ask_for_mic, device)  # dialogs must run on the main thread

    def _ask_for_mic(self, device: str):
        others = [d for d in self.dictation.recorder.input_devices() if d != device]
        message = "It recorded only silence. Is the lid closed, or the mic muted or unplugged?"
        if not others:
            rumps.alert(f"No audio from {device}", message + "\n\nConnect another microphone and try again.")
            return
        choice = rumps.alert(
            title=f"No audio from {device}",
            message=message + "\n\nSwitch to another microphone? (All mics are in the LocalFlow menu.)",
            ok=others[0],
            other=others[1] if len(others) > 1 else None,
            cancel="Keep current",
        )
        if choice == 1:
            self.set_mic(others[0])
        elif choice == -1:
            self.set_mic(others[1])


def run(cfg: Config):
    MenuBarApp(cfg).run()
