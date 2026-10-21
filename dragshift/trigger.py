"""Watches for mouse drag + modifier keys (Shift, Ctrl, Alt) anywhere on screen.
Shift + drag -> pops up SuperDrag on Convert ring.
Ctrl + drag (or swipe + ctrl) -> pops up SuperDrag on Actions ring (LocalSend, Float, Copy, Move, Copy Path, Terminal).
While menu is open:
Tapping Ctrl -> switches to Actions ring.
Tapping Shift -> switches to Convert ring.
Tapping Alt -> switches to Tools ring.
Windows: GetAsyncKeyState. macOS: NSEvent. Linux: X11 / Wayland fallback."""
from __future__ import annotations

import ctypes
import sys

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

VK_LBUTTON = 0x01
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_ESCAPE = 0x1B

DRAG_THRESHOLD = 10   # px the mouse must travel with the button held
NO_DRAG_TIMEOUT = 50  # ticks (≈ 0.75 s) to wait for a file drag to enter before hiding


class DragShiftWatcher(QObject):
    show_menu = Signal(QPoint, str)  # pos, target_ring ("Convert" or "Actions")
    toggle_ring = Signal()
    switch_ring = Signal(str)        # ring name ("Convert", "Tools", "Actions")
    hide_menu = Signal()

    def __init__(self, menu_visible, menu_got_drag, parent=None):
        super().__init__(parent)
        self.menu_visible = menu_visible
        self.menu_got_drag = menu_got_drag
        self.enabled = True
        self.vk = VK_SHIFT
        self.key_name = "shift"
        self._down_at: QPoint | None = None
        self._shift_was = False
        self._ctrl_was = False
        self._alt_was = False
        self._fired = False
        self._idle_ticks = 0
        self._shown_at = QPoint()
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._mac = None
        if sys.platform == "darwin":
            from . import platform_mac
            self._mac = platform_mac if platform_mac.OK else None
        elif sys.platform.startswith("linux"):
            from . import platform_linux
            self._mac = platform_linux if platform_linux.available() else None
        self.timer = QTimer(self, interval=15, timeout=self._tick)

    def set_key(self, name: str):
        self.key_name = name
        self.vk = {"shift": VK_SHIFT, "ctrl": VK_CONTROL, "alt": VK_MENU}.get(name, VK_SHIFT)

    def start(self):
        if self._user32 is not None or self._mac is not None:
            self.timer.start()

    def _down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _state(self) -> tuple[bool, bool, bool, bool, bool]:
        """(left button, shift, ctrl, alt, escape)"""
        if self._mac is not None:
            m = self._mac
            shift = m.key_down("shift") if hasattr(m, "key_down") else False
            ctrl = m.key_down("ctrl") if hasattr(m, "key_down") else False
            alt = m.key_down("alt") if hasattr(m, "key_down") else False
            esc = m.escape_down() if hasattr(m, "escape_down") else False
            return m.left_button_down(), shift, ctrl, alt, esc
        return (
            self._down(VK_LBUTTON),
            self._down(VK_SHIFT),
            self._down(VK_CONTROL),
            self._down(VK_MENU),
            self._down(VK_ESCAPE),
        )

    def _tick(self):
        lbtn, shift, ctrl, alt, esc = self._state()
        pos = QCursor.pos()

        trigger_down = self._down(self.vk) if self._user32 else (shift if self.key_name == "shift" else ctrl)

        if self.menu_visible():
            if not lbtn or esc:
                # drop happened (or was cancelled) – give the drop event a moment to land
                QTimer.singleShot(120, self.hide_menu.emit)
            elif ctrl and not self._ctrl_was and self.menu_got_drag():
                self.switch_ring.emit("Actions")
            elif shift and not self._shift_was and self.menu_got_drag():
                self.switch_ring.emit("Convert")
            elif alt and not self._alt_was and self.menu_got_drag():
                self.switch_ring.emit("Tools")
            elif not self.menu_got_drag() and (pos - self._shown_at).manhattanLength() > 6:
                # the cursor is moving over us but no file drag arrived: it's a window
                # move or text selection, so get out of the way
                self._idle_ticks += 1
                if self._idle_ticks > NO_DRAG_TIMEOUT:
                    self.hide_menu.emit()
        else:
            if lbtn:
                if self._down_at is None:
                    self._down_at = pos
                    self._fired = False
                moved = (pos - self._down_at).manhattanLength() >= DRAG_THRESHOLD
                if self.enabled and moved and not self._fired:
                    if ctrl:
                        self._fired = True
                        self._idle_ticks = 0
                        self._shown_at = pos
                        self.show_menu.emit(pos, "Actions")
                    elif shift or trigger_down:
                        self._fired = True
                        self._idle_ticks = 0
                        self._shown_at = pos
                        self.show_menu.emit(pos, "Convert")
            else:
                self._down_at = None
                self._fired = False
        self._shift_was = shift
        self._ctrl_was = ctrl
        self._alt_was = alt


SuperDragWatcher = DragShiftWatcher
