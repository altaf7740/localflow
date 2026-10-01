import time

from AppKit import NSPasteboard, NSPasteboardTypeString
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    CGEventSetFlags,
    kCGEventFlagMaskCommand,
    kCGHIDEventTap,
)

V_KEYCODE = 9


def _cmd_v():
    for down in (True, False):
        event = CGEventCreateKeyboardEvent(None, V_KEYCODE, down)
        CGEventSetFlags(event, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, event)


def paste_text(text: str):
    """Paste into the focused app, then restore the user's clipboard."""
    pb = NSPasteboard.generalPasteboard()
    previous = pb.stringForType_(NSPasteboardTypeString)
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    _cmd_v()
    time.sleep(0.3)
    if previous is not None:
        pb.clearContents()
        pb.setString_forType_(previous, NSPasteboardTypeString)
