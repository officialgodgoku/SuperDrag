"""Persistent settings + the Settings and Welcome windows."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout)

from . import __version__
from .util import CONFIG
from .window import GlassWindow

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP = "SuperDrag"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "output": "next",
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "trigger": "shift",
    "welcomed": False,
    "hw_accel": "off",
    "video_preset": "veryfast",
    "contribute_url": "https://buymeacoffee.com/officialgodgoku",
}


class Settings:
    def __init__(self):
        self.q = QSettings(APP, APP)

    def get(self, key):
        v = self.q.value(key, DEFAULTS[key])
        d = DEFAULTS[key]
        if isinstance(d, bool):
            return v in (True, "true", "1", 1)
        if isinstance(d, int):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d
        return v

    def set(self, key, value):
        self.q.setValue(key, value)
        self.apply()

    def apply(self):
        for k in ("output", "jpg_quality", "pdf_dpi", "hw_accel", "video_preset"):
            CONFIG[k] = self.get(k)


# ---------------------------------------------------------------- autostart (Windows)
def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --quiet'
    return f'"{sys.executable}" -m dragshift --quiet'


def autostart_enabled() -> bool:
    if IS_LINUX:
        from . import platform_linux
        return platform_linux.autostart_enabled()
    if IS_MAC:
        from . import platform_mac
        return platform_mac.autostart_enabled()
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def set_autostart(on: bool):
    if IS_LINUX:
        from . import platform_linux
        platform_linux.set_autostart(on)
        return
    if IS_MAC:
        from . import platform_mac
        platform_mac.set_autostart(on)
        return
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


TRIGGERS = ([("shift", "Shift ⇧"), ("ctrl", "Control ⌃"), ("alt", "Option ⌥")] if IS_MAC
            else [("shift", "Shift"), ("ctrl", "Ctrl"), ("alt", "Alt")])
OUTPUTS = [("next", "Next to the original"), ("folder", "In a “SuperDrag” subfolder")]
DPIS = [(150, "150 dpi · small"), (200, "200 dpi · balanced"), (300, "300 dpi · print")]
HW_ACCEL_OPTIONS = [
    ("off", "Disabled (CPU · standard)"),
    ("auto", "Auto-detect (GPU acceleration)"),
    ("qsv", "Intel QuickSync (QSV)"),
    ("nvenc", "NVIDIA NVENC"),
    ("amf", "AMD AMF"),
]
VIDEO_PRESETS = [
    ("veryfast", "Fast (recommended)"),
    ("fast", "Balanced"),
    ("medium", "Slow (smallest size)"),
]


class SettingsWindow(GlassWindow):
    changed = Signal()

    def __init__(self, settings: Settings):
        super().__init__("Settings", size=(540, 520))
        self.s = settings
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        r = 0

        def combo(options, current):
            c = QComboBox()
            for v, label in options:
                c.addItem(label, v)
            idx = max(0, [v for v, _ in options].index(current) if current in [v for v, _ in options] else 0)
            c.setCurrentIndex(idx)
            return c

        grid.addWidget(QLabel("Open the menu with"), r, 0)
        self.trigger = combo(TRIGGERS, self.s.get("trigger"))
        self.trigger.currentIndexChanged.connect(lambda _: self._save("trigger", self.trigger.currentData()))
        grid.addWidget(self.trigger, r, 1)
        r += 1
        hint = QLabel("…pressed while you’re dragging a file")
        hint.setObjectName("dim")
        grid.addWidget(hint, r, 1)
        r += 1

        grid.addWidget(QLabel("Save results"), r, 0)
        self.output = combo(OUTPUTS, self.s.get("output"))
        self.output.currentIndexChanged.connect(lambda _: self._save("output", self.output.currentData()))
        grid.addWidget(self.output, r, 1)
        r += 1

        grid.addWidget(QLabel("JPG / WebP quality"), r, 0)
        row = QHBoxLayout()
        self.q = QSlider(Qt.Horizontal)
        self.q.setRange(60, 100)
        self.q.setValue(self.s.get("jpg_quality"))
        self.qv = QLabel(str(self.q.value()))
        self.qv.setObjectName("dim")
        self.qv.setFixedWidth(30)
        self.q.valueChanged.connect(lambda v: (self.qv.setText(str(v)), self._save("jpg_quality", v)))
        row.addWidget(self.q)
        row.addWidget(self.qv)
        grid.addLayout(row, r, 1)
        r += 1

        grid.addWidget(QLabel("PDF → image resolution"), r, 0)
        self.dpi = combo(DPIS, self.s.get("pdf_dpi"))
        self.dpi.currentIndexChanged.connect(lambda _: self._save("pdf_dpi", self.dpi.currentData()))
        grid.addWidget(self.dpi, r, 1)
        r += 1

        grid.addWidget(QLabel("Video hardware acceleration"), r, 0)
        self.hw_accel = combo(HW_ACCEL_OPTIONS, self.s.get("hw_accel"))
        self.hw_accel.currentIndexChanged.connect(lambda _: self._save("hw_accel", self.hw_accel.currentData()))
        grid.addWidget(self.hw_accel, r, 1)
        r += 1

        grid.addWidget(QLabel("Video compression speed"), r, 0)
        self.video_preset = combo(VIDEO_PRESETS, self.s.get("video_preset"))
        self.video_preset.currentIndexChanged.connect(lambda _: self._save("video_preset", self.video_preset.currentData()))
        grid.addWidget(self.video_preset, r, 1)
        r += 1

        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox("Start SuperDrag with Windows" if IS_WIN else "Open SuperDrag at login")
            self.auto.setChecked(autostart_enabled())
            self.auto.toggled.connect(set_autostart)
            grid.addWidget(self.auto, r, 1)
            r += 1
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                glass_btn = QPushButton("Enable full liquid glass…")
                glass_btn.setToolTip("Lets the glass refract the windows behind it (Screen Recording permission)")
                glass_btn.clicked.connect(platform_mac.request_screen_recording)
                grid.addWidget(glass_btn, r, 1)
                r += 1
        grid.addWidget(QLabel("Contributions"), r, 0)
        c_row = QHBoxLayout()
        c_btn = QPushButton("☕ Buy Me a Coffee (officialgodgoku) ↗")
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        c_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.s.get("contribute_url"))))
        c_row.addWidget(c_btn)
        c_row.addStretch(1)
        grid.addLayout(c_row, r, 1)
        r += 1

        self.body.addLayout(grid)
        self.body.addStretch(1)
        about = QLabel(f"SuperDrag {__version__}  ·  Created by Manish  ·  Originals are never modified")
        about.setObjectName("dim")
        foot = QHBoxLayout()
        foot.addWidget(about)
        foot.addStretch(1)
        done = QPushButton("Done")
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        foot.addWidget(done)
        self.body.addLayout(foot)

    def _save(self, key, value):
        self.s.set(key, value)
        self.changed.emit()


class WelcomeWindow(GlassWindow):
    def __init__(self, settings: Settings, trigger_label: str = "Shift"):
        super().__init__("Welcome to SuperDrag", size=(560, 430))
        self.s = settings
        steps = [
            ("1", "Start dragging any file", "in Finder or on the desktop" if IS_MAC else
             "in your file manager (Thunar, Nautilus…)" if IS_LINUX else "in File Explorer or on the desktop"),
            ("2", f"Press {trigger_label}", "the glass menu opens right under your cursor"),
            ("3", "Drop it on a slice", "the result is saved next to the original"),
            ("⇄", f"Tap {trigger_label} again", "to switch between Convert and Tools"),
        ]
        for n, head, sub in steps:
            row = QHBoxLayout()
            badge = QLabel(n)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(34, 34)
            badge.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5ac8ff, stop:1 #2f7bff);"
                                "border-radius: 17px; font-weight: 700; font-size: 12pt;")
            row.addWidget(badge)
            col = QVBoxLayout()
            col.setSpacing(0)
            h = QLabel(head)
            h.setStyleSheet("font-size: 12pt; font-weight: 600;")
            d = QLabel(sub)
            d.setObjectName("dim")
            col.addWidget(h)
            col.addWidget(d)
            row.addSpacing(8)
            row.addLayout(col, 1)
            self.body.addLayout(row)
        self.body.addStretch(1)
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                note = QLabel("Optional: allow Screen Recording so the glass can refract the windows "
                              "behind it (otherwise it shows your wallpaper). SuperDrag never saves or sends it.")
                note.setObjectName("dim")
                note.setWordWrap(True)
                self.body.addWidget(note)
                b = QPushButton("Allow Screen Recording…")
                b.clicked.connect(platform_mac.request_screen_recording)
                self.body.addWidget(b, 0, Qt.AlignLeft)
        if IS_LINUX:
            from . import platform_linux
            if platform_linux.is_wayland():
                note = QLabel("You're on a Wayland session: the Shift-while-dragging trigger needs X11 (e.g. XFCE). "
                              "Right-click a file → Open With → SuperDrag still works.")
                note.setObjectName("warn")
                note.setWordWrap(True)
                self.body.addWidget(note)
        foot = QHBoxLayout()
        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox("Start with Windows" if IS_WIN else "Open at login")
            self.auto.setChecked(True)
            foot.addWidget(self.auto)
        foot.addStretch(1)
        credit = QLabel("Created by Manish")
        credit.setObjectName("dim")
        foot.addWidget(credit)
        foot.addSpacing(16)
        ok = QPushButton("Got it")
        ok.setObjectName("primary")
        ok.clicked.connect(self._done)
        foot.addWidget(ok)
        self.body.addLayout(foot)

    def _done(self):
        self.s.set("welcomed", True)
        if IS_WIN or IS_MAC or IS_LINUX:
            set_autostart(self.auto.isChecked())
        self.close()


class DropZone(QLabel):
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(130)
        self._hover = False
        self._update_style()
        self.setText("⚡ Drop any file(s) here to open the SuperDrag dial\n\nor click anywhere here to choose files")

    def _update_style(self):
        border = "#5ac8ff" if self._hover else "rgba(255, 255, 255, 0.28)"
        bg = "rgba(90, 200, 255, 0.15)" if self._hover else "rgba(255, 255, 255, 0.04)"
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px dashed {border};
                border-radius: 14px;
                background: {bg};
                color: #ffffff;
                font-size: 11pt;
                font-weight: 500;
                padding: 16px;
            }}
        """)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            self._hover = True
            self._update_style()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._hover = False
        self._update_style()

    def dropEvent(self, e):
        self._hover = False
        self._update_style()
        files = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile() and u.toLocalFile()]
        if files:
            self.files_dropped.emit(files)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class HubWindow(GlassWindow):
    open_files = Signal(list)
    open_settings_requested = Signal()
    open_welcome_requested = Signal()
    open_about_requested = Signal()

    def __init__(self, settings: Settings, trigger_label: str = "Shift"):
        super().__init__("SuperDrag", size=(620, 520))
        self.s = settings

        # Header title with status badge
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        h1 = QLabel("SuperDrag")
        h1.setStyleSheet("font-size: 20pt; font-weight: 700; color: #ffffff;")
        sub = QLabel(f"Hold {trigger_label} while dragging any file · Created by Manish")
        sub.setObjectName("dim")
        title_box.addWidget(h1)
        title_box.addWidget(sub)
        header.addLayout(title_box)
        header.addStretch(1)

        status = QLabel("● Active")
        status.setStyleSheet(
            "background: rgba(46, 213, 115, 0.2); color: #2ed573; "
            "border: 1px solid rgba(46, 213, 115, 0.4); border-radius: 12px; "
            "padding: 4px 12px; font-weight: 600; font-size: 10pt;"
        )
        header.addWidget(status)
        self.body.addLayout(header)

        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.files_dropped.connect(lambda fs: self.open_files.emit(fs))
        self.drop_zone.clicked.connect(self._on_browse)
        self.body.addWidget(self.drop_zone)

        # Shortcuts quick guide
        cards = QHBoxLayout()
        cards.setSpacing(10)

        guide_items = [
            ("Shift + Drag", "Convert Dial", "Images, Videos, PDFs, Audio, Docs"),
            ("Ctrl + Drag", "Actions Dial", "LocalSend, Floating Shelf, Copy, Terminal"),
            ("Alt + Drag", "Tools Dial", "Compress, Crop, Redact, Protect, Split"),
        ]
        for key_title, ring_name, desc in guide_items:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(255, 255, 255, 0.12);
                    border-radius: 10px;
                }
            """)
            clayout = QVBoxLayout(card)
            clayout.setSpacing(3)
            clayout.setContentsMargins(10, 10, 10, 10)
            k = QLabel(key_title)
            k.setStyleSheet("font-weight: 700; color: #5ac8ff; font-size: 10pt;")
            r = QLabel(ring_name)
            r.setStyleSheet("font-weight: 600; color: #ffffff; font-size: 9pt;")
            d = QLabel(desc)
            d.setObjectName("dim")
            d.setStyleSheet("font-size: 8pt;")
            d.setWordWrap(True)
            clayout.addWidget(k)
            clayout.addWidget(r)
            clayout.addWidget(d)
            cards.addWidget(card, 1)
        self.body.addLayout(cards)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        settings_btn = QPushButton("⚙ Settings…")
        settings_btn.clicked.connect(lambda: self.open_settings_requested.emit())
        btn_row.addWidget(settings_btn)

        help_btn = QPushButton("📖 How to Use")
        help_btn.clicked.connect(lambda: self.open_welcome_requested.emit())
        btn_row.addWidget(help_btn)

        about_btn = QPushButton("ⓘ About")
        about_btn.clicked.connect(lambda: self.open_about_requested.emit())
        btn_row.addWidget(about_btn)

        contribute_btn = QPushButton("☕ Contribute")
        contribute_btn.setToolTip("Support development on Buy Me a Coffee")
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        contribute_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.s.get("contribute_url"))))
        btn_row.addWidget(contribute_btn)

        btn_row.addStretch(1)

        hide_btn = QPushButton("Keep Running in Tray")
        hide_btn.setObjectName("primary")
        hide_btn.clicked.connect(self.close)
        btn_row.addWidget(hide_btn)

        self.body.addLayout(btn_row)

        # Footer
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 4, 0, 0)
        accel = self.s.get("hw_accel")
        accel_label = dict(HW_ACCEL_OPTIONS).get(accel, "CPU")
        credit = QLabel(f"SuperDrag 1.1.0 · Created by Manish · Video Accel: {accel_label}")
        credit.setObjectName("dim")
        foot.addWidget(credit)
        self.body.addLayout(foot)

    def _on_browse(self):
        from PySide6.QtWidgets import QFileDialog
        from PySide6.QtCore import QDir
        files, _ = QFileDialog.getOpenFileNames(self, "Choose file(s) for SuperDrag", QDir.homePath())
        if files:
            self.open_files.emit(files)


class AboutWindow(GlassWindow):
    def __init__(self, settings: Settings):
        super().__init__("About SuperDrag", size=(520, 390))
        self.s = settings

        center_col = QVBoxLayout()
        center_col.setAlignment(Qt.AlignCenter)
        center_col.setSpacing(6)

        title = QLabel("SuperDrag")
        title.setStyleSheet("font-size: 26pt; font-weight: 800; color: #ffffff;")
        title.setAlignment(Qt.AlignCenter)

        ver = QLabel(f"Version {__version__}")
        ver.setStyleSheet("font-size: 11pt; color: #5ac8ff; font-weight: 600;")
        ver.setAlignment(Qt.AlignCenter)

        credit = QLabel("Created by Manish")
        credit.setStyleSheet("font-size: 13pt; font-weight: 700; color: #ffffff; padding: 4px;")
        credit.setAlignment(Qt.AlignCenter)

        desc = QLabel(
            "Fluid 3D Liquid-Glass Drag-and-Drop conversion & action utility.\n\n"
            "• Hold Shift while dragging to open Convert Dial\n"
            "• Hold Ctrl while dragging to open Actions Dial\n"
            "• Hold Alt while dragging to open Tools Dial\n\n"
            "Original files are never overwritten or modified."
        )
        desc.setObjectName("dim")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)

        accel = self.s.get("hw_accel")
        accel_label = dict(HW_ACCEL_OPTIONS).get(accel, "CPU")
        status_box = QLabel(f"Hardware Acceleration: {accel_label}")
        status_box.setStyleSheet(
            "background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.15); "
            "border-radius: 8px; padding: 6px 14px; font-size: 9pt; color: #a0c4ff;"
        )
        status_box.setAlignment(Qt.AlignCenter)

        center_col.addWidget(title)
        center_col.addWidget(ver)
        center_col.addWidget(credit)
        center_col.addSpacing(6)
        center_col.addWidget(desc)
        center_col.addSpacing(8)
        center_col.addWidget(status_box)
        center_col.addSpacing(10)

        bmac_btn = QPushButton("☕ Support Developer (Buy Me a Coffee)")
        bmac_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffd214, stop:1 #ffb800);
                color: #1a1a1a;
                font-weight: 700;
                font-size: 10pt;
                border: 1px solid rgba(255, 255, 255, 0.4);
                border-radius: 8px;
                padding: 7px 18px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffe033, stop:1 #ffc726);
                border: 1px solid #ffffff;
            }
        """)
        bmac_btn.setCursor(Qt.PointingHandCursor)
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        bmac_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.s.get("contribute_url"))))
        center_col.addWidget(bmac_btn)

        self.body.addLayout(center_col)
        self.body.addStretch(1)

        foot = QHBoxLayout()
        foot.addStretch(1)
        close_btn = QPushButton("Done")
        close_btn.setObjectName("primary")
        close_btn.clicked.connect(self.close)
        foot.addWidget(close_btn)
        self.body.addLayout(foot)
