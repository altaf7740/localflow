import sys

from .config import Config


def main():
    cfg = Config.load()
    if sys.platform == "darwin":
        from .ui_mac import run
    else:
        from .ui_tray import run
    run(cfg)


if __name__ == "__main__":
    main()
