import sys
import time

if sys.platform == "darwin":
    from AppKit import NSPasteboard, NSPasteboardTypeString
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )
else:
    import pyperclip
    from pynput.keyboard import Controller, Key

V_KEYCODE = 9


def paste_text(text: str):
    """Paste into the focused app, then restore the user's clipboard."""
    if sys.platform == "darwin":
        _paste_mac(text)
    else:
        _paste_generic(text)


def _paste_mac(text: str):
    pb = NSPasteboard.generalPasteboard()
    previous = pb.stringForType_(NSPasteboardTypeString)
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    for down in (True, False):
        event = CGEventCreateKeyboardEvent(None, V_KEYCODE, down)
        CGEventSetFlags(event, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event)
    time.sleep(0.3)
    if previous is not None:
        pb.clearContents()
        pb.setString_forType_(previous, NSPasteboardTypeString)


def _paste_generic(text: str):
    try:
        previous = pyperclip.paste()
    except pyperclip.PyperclipException:
        previous = None
    pyperclip.copy(text)
    keyboard = Controller()
    with keyboard.pressed(Key.ctrl):
        keyboard.tap("v")
    time.sleep(0.3)
    if previous:
        pyperclip.copy(previous)
