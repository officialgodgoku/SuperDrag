"""SuperDrag: Shift+drag any file to convert or edit it from a radial liquid-glass menu."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QDir, QObject, QPointF, QRunnable, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import (QAction, QColor, QCursor, QDesktopServices, QGuiApplication, QIcon, QPainter,
                           QPixmap)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QSystemTrayIcon, QWidget

from . import __version__, convert, glass, imaging, report, tools
from .radial import Item, RadialMenu
from .settings import AboutWindow, HubWindow, Settings, SettingsWindow, WelcomeWindow, TRIGGERS
from .toasts import ToastStack
from .trigger import DragShiftWatcher, DragShiftWatcher as SuperDragWatcher
from .util import UserError, category, file_size, human_size, keep, release

APP_NAME = "SuperDrag"
AUTHOR = "Manish"
VERSION = __version__
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
from .handoff import ipc_name
IPC_NAME = ipc_name()

GLYPHS = {
    # Image tools
    "Compress": "⇲", "Metadata": "ⓘ", "Redact": "▮", "Crop": "⌗", "Edit": "☼",
    "Annotate": "✎", "Add BG": "▣", "Remove BG": "🪄", "Resize": "⤢",
    # PDF tools
    "Split": "✂", "Rotate": "⟳", "Merge": "⧉", "Protect": "⚿", "Extract": "⧈", "Organize": "📑",
    # Video tools
    "Mute": "🔇", "Extract Audio": "♬", "Trim": "✂", "Speed": "⏩", "Snapshot": "📷",
    # Audio tools
    "Normalize": "🎚", "Visualize": "〰", "Channels": "⇄", "Bleep": "🔔",
    # Archive tools
    "Extract Here": "📂", "Extract to Folder": "📁",
    # Actions ring
    "LocalSend": "📡", "AirDrop": "📡", "Float": "📌", "Copy": "📋", "Move": "➜", "Copy Path": "🔗", "Terminal": "💻",
}

HINTS = {
    # Image
    "Compress": "Shrink file size", "Metadata": "View · remove GPS", "Redact": "Hide private info",
    "Crop": "Trim or crop", "Edit": "Light · colour · rotate", "Annotate": "Arrows · text · steps",
    "Add BG": "Gradient backdrop", "Remove BG": "Remove background · cutout", "Resize": "Change dimensions",
    # PDF
    "Split": "One PDF per page", "Rotate": "Turn pages 90°", "Merge": "Join into one PDF",
    "Protect": "Add a password", "Extract": "Save embedded images", "Organize": "Rearrange or split pages",
    # Video
    "Mute": "Remove audio track", "Extract Audio": "Save as MP3 audio", "Trim": "Cut first 30s",
    "Speed": "Change speed 2x", "Snapshot": "Save frame as PNG",
    # Audio
    "Normalize": "Even out peak volume", "Visualize": "Export waveform image",
    "Channels": "Convert to Mono", "Bleep": "Censor tone on segment",
    # Archive
    "Extract Here": "Unpack archive here", "Extract to Folder": "Unpack into subfolder",
    # Actions
    "LocalSend": "Share via LocalSend", "AirDrop": "Share via AirDrop",
    "Float": "Pin to floating shelf", "Copy": "Copy to clipboard",
    "Move": "Move to folder…", "Copy Path": "Copy path to clipboard",
    "Terminal": "Open in Terminal",
}

FORMAT_HINTS = {
    # Images
    "JPG": "Small, universal", "PNG": "Lossless · transparency", "WEBP": "Smallest for web",
    "HEIC": "iPhone format", "TIFF": "Print · archival", "AVIF": "Next-gen, tiny",
    "BMP": "Uncompressed", "PDF": "Document", "ICO": "Windows icon", "GIF": "Animated / web",
    # Video
    "MP4": "Universal video (H.264)", "WEBM": "Web video (VP9)", "MOV": "Apple QuickTime",
    "MKV": "Matroska container", "AVI": "Classic video", "WMV": "Windows Media Video",
    # Audio
    "MP3": "Universal audio", "M4A": "Apple AAC audio", "WAV": "Lossless PCM",
    "FLAC": "Lossless audio", "OGG": "Vorbis audio", "OPUS": "Efficient voice/music",
    "AIFF": "Apple uncompressed", "WMA": "Windows Media Audio",
    # Documents
    "DOCX": "Editable Word document", "PAGES": "Apple Pages format", "PPTX": "PowerPoint presentation",
    "PPT": "PowerPoint 97-2003", "XLSX": "Excel spreadsheet", "ODS": "OpenDocument spreadsheet",
    "CSV": "Comma-separated values", "TSV": "Tab-separated values", "EPUB": "E-book format",
    "TXT": "Plain text", "MD": "Markdown document", "HTML": "Web document",
    # Subtitles
    "SRT": "SubRip subtitles", "VTT": "WebVTT subtitles",
    # Archives
    "ZIP": "Standard Zip archive", "ZIP (Deflate)": "Standard Zip archive", "ZIP (Max)": "Max compression (L9)",
    "ZIP (Store)": "Store without compression", "ZIP (BZIP2)": "Bzip2 compression",
    "ZIP (LZMA)": "LZMA ultra compression", "TAR.GZ": "Gzipped Tarball", "TAR": "Uncompressed Tarball",
}

IMAGE_TOOLS = ["Compress", "Resize", "Crop", "Edit", "Annotate", "Redact", "Add BG", "Remove BG", "Metadata"]
VIDEO_TOOLS = ["Compress", "Metadata", "Mute", "Trim", "Crop", "Speed", "Snapshot", "Split", "Redact"]
AUDIO_TOOLS = ["Compress", "Metadata", "Normalize", "Visualize", "Trim", "Channels", "Bleep"]
PDF_TOOLS = ["Compress", "Metadata", "Split", "Organize", "Rotate", "Protect", "Extract"]
ARCHIVE_TOOLS = ["Extract Here", "Extract to Folder"]


# ---------------------------------------------------------------- background jobs
class _Sig(QObject):
    done = Signal(object)
    failed = Signal(str)


class Job(QRunnable):
    def __init__(self, action: str, srcs: list, fn, extra: str = ""):
        super().__init__()
        self.action, self.srcs, self.fn, self.extra = action, srcs, fn, extra
        self.sig = _Sig()

    def run(self):
        try:
            outs = self.fn() or []
            self.sig.done.emit(report.summarize(self.action, self.srcs, outs, self.extra))
        except UserError as e:
            self.sig.failed.emit(str(e))
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.sig.failed.emit(friendly_error(e))


def friendly_error(e: Exception) -> str:
    msg = str(e) or e.__class__.__name__
    low = msg.lower()
    if isinstance(e, PermissionError) or "permission denied" in low:
        return "No permission to write next to this file. Try a folder you own, or set Settings → Save results → subfolder."
    if "cannot identify image" in low:
        return "This file doesn't look like an image SuperDrag can read."
    if isinstance(e, FileNotFoundError):
        return "The file was moved or deleted."
    return msg


# ---------------------------------------------------------------- icon
def make_tray_icon() -> QIcon:
    """macOS menu bar wants a monochrome 'template' image; Windows gets the colour icon."""
    if not IS_MAC:
        return make_icon()
    pm = QPixmap(44, 44)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor(0, 0, 0), 4.5))
    p.drawEllipse(QPointF(22, 22), 14, 14)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0))
    p.drawEllipse(QPointF(22, 22), 5, 5)
    for a in range(0, 360, 45):  # petal gaps
        import math
        x, y = 22 + 14 * math.cos(math.radians(a + 22.5)), 22 + 14 * math.sin(math.radians(a + 22.5))
        p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
    p.end()
    pm.setDevicePixelRatio(2.0)
    icon = QIcon(pm)
    icon.setIsMask(True)
    return icon


def make_icon() -> QIcon:
    for name in ("superdrag.ico", "dragshift.ico"):
        ico = Path(__file__).with_name("assets") / name
        if ico.exists():
            return QIcon(str(ico))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(glass.iridescent_pen(QPointF(32, 32), 7, 255))
    p.drawEllipse(QPointF(32, 32), 24, 24)
    p.end()
    return QIcon(pm)


# ---------------------------------------------------------------- the app
class SuperDragApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.settings.apply()
        self.pool = QThreadPool.globalInstance()
        self.windows: list[QWidget] = []
        self._hub = None
        self._shelf = None
        self.toasts = ToastStack()
        self.menu = RadialMenu(self.build_rings, self.describe)
        self.menu.activated.connect(self.run_item)

        # the watcher only manages menus it opened (drag mode); click-mode menus (tray, right-click,
        # Send To) must not be closed just because no mouse button is held
        self.watcher = SuperDragWatcher(lambda: self.menu.isVisible() and not self.menu.click_mode,
                                        lambda: self.menu.got_drag, self)
        self.watcher.set_key(self.settings.get("trigger"))
        self.watcher.show_menu.connect(lambda pos, ring="Convert": self.menu.popup(pos, ring=ring))
        self.watcher.toggle_ring.connect(self.menu.next_ring)
        self.watcher.switch_ring.connect(self.menu.set_ring)
        self.watcher.hide_menu.connect(self.menu.close_menu)
        self.watcher.start()

        # files handed over by "Send to", the right-click menu, or a second launch
        self._pending: list[str] = []
        self._pending_timer = QTimer(self, singleShot=True, interval=280, timeout=self._flush_pending)
        self.server = QLocalServer(self)
        QLocalServer.removeServer(IPC_NAME)
        self.server.listen(IPC_NAME)
        self.server.newConnection.connect(self._ipc)

        self.tray = QSystemTrayIcon(make_tray_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} by Manish — press {self.trigger_label()} while dragging a file")
        m = QMenu()
        m.setStyleSheet(glass.QSS)
        self.act_enabled = QAction("Enabled", m, checkable=True, checked=True)
        self.act_enabled.toggled.connect(lambda on: setattr(self.watcher, "enabled", on))
        m.addAction(self.act_enabled)
        m.addAction("Open SuperDrag Hub", self.open_hub)
        m.addAction("Open a file…", self.open_dialog)
        m.addSeparator()
        m.addAction("Settings…", self.open_settings)
        m.addAction("How to use", self.show_welcome)
        m.addAction("About SuperDrag (by Manish)", self.show_about)
        m.addAction("Support & Contribute ☕", lambda: QDesktopServices.openUrl(QUrl(self.settings.get("contribute_url"))))
        m.addSeparator()
        m.addAction(f"Quit {APP_NAME}", self.qapp.quit)
        self.tray_menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self._tray_click)
        self.tray.show()

    def trigger_label(self) -> str:
        return dict(TRIGGERS).get(self.settings.get("trigger"), "Shift")

    # ------------------------------------------------------------ IPC
    def _ipc(self):
        sock = self.server.nextPendingConnection()
        if sock is None:
            return
        buf = bytearray()
        done = {"v": False}

        def consume():
            if done["v"]:
                return
            try:
                buf.extend(bytes(sock.readAll()))
            except RuntimeError:
                pass
            try:
                data = json.loads(buf.decode("utf-8"))
            except Exception:
                return  # incomplete: wait for more
            done["v"] = True
            files = [f for f in data.get("files", []) if os.path.exists(f)]
            print(f"IPC: {len(files)} file(s) handed over", flush=True)
            if files:
                self.queue_files(files)
            elif data.get("show"):
                self.open_hub()
            sock.disconnectFromServer()
            sock.deleteLater()

        # Windows pipes: the sender may already be gone, so read on every signal + a fallback timer
        sock.readyRead.connect(consume)
        sock.disconnected.connect(consume)
        for ms in (0, 50, 200, 600):
            QTimer.singleShot(ms, consume)

    def queue_files(self, files: list[str]):
        """Explorer's right-click menu launches once per file: gather them, then show one menu."""
        for f in files:
            if f not in self._pending:
                self._pending.append(f)
        self._pending_timer.start()

    def _flush_pending(self):
        files, self._pending = self._pending, []
        if files:
            self.show_click_menu(files)

    # ------------------------------------------------------------ menu contents
    def describe(self, paths: list[str]) -> str:
        if len(paths) > 1:
            return f"{len(paths)} files"
        return human_size(file_size(paths[0]))

    def get_shelf(self):
        if self._shelf is None:
            from .shelf import FloatingShelfWindow
            self._shelf = FloatingShelfWindow()
            self.windows.append(self._shelf)
        return self._shelf

    def build_rings(self, paths: list[str]) -> dict[str, list[Item]]:
        cat = category(paths[0])
        action_name = "AirDrop" if IS_MAC else "LocalSend"
        action_key = "action:airdrop" if IS_MAC else "action:localsend"
        action_items = [
            Item(action_name, GLYPHS.get(action_name, "📡"), key=action_key, hint=HINTS.get(action_name, "")),
            Item("Float", GLYPHS.get("Float", "📌"), key="action:float", hint=HINTS.get("Float", "")),
            Item("Copy", GLYPHS.get("Copy", "📋"), key="action:copy", hint=HINTS.get("Copy", "")),
            Item("Move", GLYPHS.get("Move", "➜"), key="action:move", hint=HINTS.get("Move", "")),
            Item("Copy Path", GLYPHS.get("Copy Path", "🔗"), key="action:copy_path", hint=HINTS.get("Copy Path", "")),
            Item("Terminal", GLYPHS.get("Terminal", "💻"), key="action:terminal", hint=HINTS.get("Terminal", "")),
        ]

        if cat is None:
            return {"Actions": action_items}

        ext = Path(paths[0]).suffix
        same = [p for p in paths if category(p) == cat]
        convert_items = []
        for t in convert.targets_for(cat, ext):
            hint = FORMAT_HINTS.get(t, FORMAT_HINTS.get(t.upper(), ""))
            if cat == "image" and t == "PDF" and len(same) > 1:
                hint = f"{len(same)} images → 1 PDF"
            convert_items.append(Item(t, key=f"convert:{t}", hint=hint))

        rings: dict[str, list[Item]] = {}
        if convert_items:
            rings["Convert"] = convert_items

        if cat == "image":
            rings["Tools"] = [Item(n, GLYPHS.get(n, "✦"), key=f"tool:{n}", hint=HINTS.get(n, "")) for n in IMAGE_TOOLS]
        elif cat == "video":
            rings["Tools"] = [Item(n, GLYPHS.get(n, "▶"), key=f"tool:{n}", hint=HINTS.get(n, "")) for n in VIDEO_TOOLS]
        elif cat == "audio":
            rings["Tools"] = [Item(n, GLYPHS.get(n, "♪"), key=f"tool:{n}", hint=HINTS.get(n, "")) for n in AUDIO_TOOLS]
        elif cat == "pdf":
            names = PDF_TOOLS[:3] + (["Merge"] if len(same) > 1 else []) + PDF_TOOLS[3:]
            rings["Tools"] = [Item(n, GLYPHS.get(n, "✦"), key=f"tool:{n}", hint=HINTS.get(n, "")) for n in names]
        elif cat == "archive":
            rings["Tools"] = [Item(n, GLYPHS.get(n, "✦"), key=f"tool:{n}", hint=HINTS.get(n, "")) for n in ARCHIVE_TOOLS]

        rings["Actions"] = action_items
        return rings

    # ------------------------------------------------------------ actions
    def run_item(self, item: Item, paths: list[str]):
        kind, name = item.key.split(":", 1)
        if kind == "action":
            from . import actions
            if name in ("localsend", "airdrop"):
                if IS_MAC:
                    actions.share_airdrop(paths)
                    self.toasts.info("AirDrop", f"{len(paths)} item(s) shared")
                else:
                    actions.share_localsend(paths)
                    self.toasts.info("LocalSend", f"{len(paths)} item(s) shared to LocalSend")
            elif name == "float":
                self.get_shelf().add_files(paths)
                self.toasts.info("Pinned to Shelf", f"{len(paths)} item(s) pinned to Float Shelf")
            elif name == "copy":
                actions.copy_files(paths)
                self.toasts.info("Copied", f"{len(paths)} item(s) copied to clipboard")
            elif name == "move":
                actions.move_files(paths)
            elif name == "copy_path":
                actions.copy_paths(paths)
                self.toasts.info("Copied Path", f"{len(paths)} path(s) copied to clipboard")
            elif name == "terminal":
                actions.open_terminal(paths[0])
            return

        cat = category(paths[0])
        paths = [p for p in paths if category(p) == cat]
        if not paths:
            return

        if kind == "convert":
            if cat == "image" and name == "PDF" and len(paths) > 1:
                self.submit(f"convert:{name}", paths, lambda: convert.images_to_single_pdf(paths),
                            f"Combining {len(paths)} images…")
            elif cat in ("folder", "archive"):
                self.submit(f"convert:{name}", paths,
                            lambda: [o for p in paths for o in convert.convert(p, cat, name)],
                            f"Compressing into {name}…")
            else:
                verb = f"Converting to {name}…"
                self.submit(f"convert:{name}", paths,
                            lambda: [o for p in paths for o in convert.convert(p, cat, name)], verb)
            return

        if kind == "tool":
            if cat == "archive":
                from . import archive
                if name == "Extract Here":
                    self.submit("tool:Extract Here", paths,
                                lambda: [o for p in paths for o in archive.extract_archive(p, to_subfolder=False)],
                                "Extracting archive…")
                elif name == "Extract to Folder":
                    self.submit("tool:Extract to Folder", paths,
                                lambda: [o for p in paths for o in archive.extract_archive(p, to_subfolder=True)],
                                "Extracting into folder…")
                return

            if cat == "video":
                from . import video
                if name == "Mute":
                    self.submit("tool:Mute", paths,
                                lambda: [o for p in paths for o in video.mute_video(p)], "Muting video…")
                elif name == "Compress":
                    self.submit("tool:Compress", paths,
                                lambda: [o for p in paths for o in video.compress_video(p)], "Compressing video…")
                elif name == "Extract Audio":
                    self.submit("tool:Extract Audio", paths,
                                lambda: [o for p in paths for o in video.convert_video(p, "MP3")], "Extracting audio…")
                elif name == "Snapshot":
                    self.submit("tool:Snapshot", paths,
                                lambda: [o for p in paths for o in video.take_snapshot(p)], "Capturing snapshot…")
                elif name == "Speed":
                    self.submit("tool:Speed", paths,
                                lambda: [o for p in paths for o in video.change_speed(p, 2.0)], "Speeding up 2x…")
                elif name == "Trim":
                    self.submit("tool:Trim", paths,
                                lambda: [o for p in paths for o in video.trim_video(p, 30)], "Trimming first 30s…")
                elif name == "Crop":
                    self.submit("tool:Crop", paths,
                                lambda: [o for p in paths for o in video.crop_video(p)], "Cropping video 1:1…")
                elif name == "Split":
                    self.submit("tool:Split", paths,
                                lambda: [o for p in paths for o in video.split_video(p, 60)], "Splitting video…")
                elif name in ("Metadata", "Redact"):
                    self.submit("tool:Clean Metadata", paths,
                                lambda: [o for p in paths for o in video.strip_metadata_video(p)], "Stripping metadata…")
                return

            if cat == "audio":
                from . import audio
                if name == "Compress":
                    self.submit("tool:Compress", paths,
                                lambda: [o for p in paths for o in audio.compress_audio(p)], "Compressing audio…")
                elif name == "Normalize":
                    self.submit("tool:Normalize", paths,
                                lambda: [o for p in paths for o in audio.normalize_audio(p)], "Normalizing audio…")
                elif name == "Visualize":
                    self.submit("tool:Visualize", paths,
                                lambda: [o for p in paths for o in audio.visualize_audio(p)], "Generating waveform…")
                elif name == "Trim":
                    self.submit("tool:Trim", paths,
                                lambda: [o for p in paths for o in audio.trim_audio(p, 30)], "Trimming audio…")
                elif name == "Channels":
                    self.submit("tool:Channels", paths,
                                lambda: [o for p in paths for o in audio.convert_channels(p)], "Converting channels…")
                elif name == "Bleep":
                    self.submit("tool:Bleep", paths,
                                lambda: [o for p in paths for o in audio.bleep_audio(p)], "Adding bleep tone…")
                elif name == "Metadata":
                    self.submit("tool:Clean Metadata", paths,
                                lambda: [o for p in paths for o in audio.strip_metadata_audio(p)], "Stripping metadata…")
                return

            if cat == "pdf":
                if name == "Merge":
                    self.submit("tool:Merge", paths, lambda: [imaging.merge_pdfs(paths)], "Merging…")
                elif name == "Metadata":
                    self.open_window(tools.MetadataWindow(paths[0], self.notify, is_pdf=True))
                elif name == "Protect":
                    self.open_window(tools.ProtectWindow(paths[0], self.notify))
                elif name == "Organize":
                    self.submit("tool:Organize", paths, imaging.split_pdf, "Splitting pages…")
                else:
                    fns = {"Compress": lambda p: [imaging.compress_pdf(p)], "Split": imaging.split_pdf,
                           "Rotate": lambda p: [imaging.rotate_pdf(p)], "Extract": imaging.extract_pdf_images}
                    f = fns[name]
                    self.submit(f"tool:{name}", paths, lambda: [o for p in paths for o in f(p)],
                                {"Compress": "Compressing…", "Split": "Splitting…", "Rotate": "Rotating…",
                                 "Extract": "Extracting images…"}[name])
                return

            windows = {"Crop": tools.CropWindow, "Add BG": tools.AddBgWindow, "Annotate": tools.AnnotateWindow,
                       "Redact": tools.RedactWindow, "Edit": tools.EditWindow, "Metadata": tools.MetadataWindow,
                       "Remove BG": tools.RemoveBgWindow}
            try:
                if name == "Compress":
                    self.open_window(tools.CompressWindow(paths, self.notify))
                elif name == "Resize":
                    self.open_window(tools.ResizeWindow(paths, self.notify))
                elif name == "Remove BG" and len(paths) > 1:
                    self.submit("tool:Remove BG", paths,
                                lambda: [imaging.remove_background_file(p) for p in paths],
                                "Removing backgrounds…")
                elif name in windows:
                    self.open_window(windows[name](paths[0], self.notify))
            except UserError as e:
                self.toasts.error(f"Couldn't open {name}", str(e))
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.toasts.error(f"Couldn't open {name}", friendly_error(e))

    def open_window(self, w: QWidget):
        if hasattr(w, "submit"):
            w.submit = self.submit
        self.windows.append(w)
        w.destroyed.connect(lambda *_: self.windows.remove(w) if w in self.windows else None)
        if hasattr(w, "present"):
            w.present()
        else:
            w.show()

    def submit(self, action: str, srcs: list, fn, working: str = "Working…", extra: str = ""):
        """Run in the background. A spinner card appears only if it takes > 150 ms."""
        state = {"card": None, "finished": False}
        names = Path(srcs[0]).name if len(srcs) == 1 else f"{len(srcs)} files"

        def show_spinner():
            if not state["finished"]:
                state["card"] = self.toasts.new()
                state["card"].working(working, names)

        QTimer.singleShot(150, show_spinner)
        job = Job(action, srcs, fn, extra)

        def done(r):
            release(job)
            state["finished"] = True
            card = state["card"] or self.toasts.new()
            card.done(r)

        def failed(msg):
            release(job)
            state["finished"] = True
            card = state["card"] or self.toasts.new()
            card.error("Couldn't finish", msg)

        job.sig.done.connect(done)
        job.sig.failed.connect(failed)
        self.pool.start(keep(job))

    def notify(self, action: str, srcs: list, outs: list, extra: str = ""):
        """Called by tool windows after they save."""
        self.toasts.new().done(report.summarize(action, srcs, outs, extra))

    # ------------------------------------------------------------ misc
    def _tray_click(self, reason):
        # macOS: a click on the menu-bar icon shows the menu; Windows: click opens Hub
        if not IS_MAC and reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_hub()

    def open_hub(self):
        try:
            alive = self._hub is not None and self._hub.isVisible()
        except RuntimeError:
            self._hub = None
            alive = False
        if not alive:
            self._hub = HubWindow(self.settings, self.trigger_label())
            self._hub.open_files.connect(self.show_click_menu)
            self._hub.open_settings_requested.connect(self.open_settings)
            self._hub.open_welcome_requested.connect(self.show_welcome)
            self._hub.open_about_requested.connect(self.show_about)
            self._hub.destroyed.connect(self._clear_hub)
            self.open_window(self._hub)
        try:
            self._hub.bring_to_front()
        except Exception:
            pass

    def _clear_hub(self, *_):
        self._hub = None

    def show_about(self):
        w = AboutWindow(self.settings)
        self.open_window(w)

    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Choose file(s) for SuperDrag", QDir.homePath())
        if files:
            self.show_click_menu(files)

    def show_click_menu(self, files: list[str]):
        g = (QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()).availableGeometry()
        pos = QCursor.pos() if g.contains(QCursor.pos()) else g.center()
        self.menu.popup(pos, files)
        self.menu.activateWindow()

    def open_settings(self):
        w = SettingsWindow(self.settings)
        w.changed.connect(self._settings_changed)
        self.open_window(w)

    def _settings_changed(self):
        self.watcher.set_key(self.settings.get("trigger"))
        self.tray.setToolTip(f"{APP_NAME} — press {self.trigger_label()} while dragging a file")

    def show_welcome(self):
        self.open_window(WelcomeWindow(self.settings, self.trigger_label()))


class SuperDragQApplication(QApplication):
    """macOS delivers files from Finder's "Open With", the Dock and `open -a` as FileOpen
    events (not argv)."""
    file_opened = Signal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.early_files: list[str] = []

    def event(self, e):
        from PySide6.QtCore import QEvent
        if e.type() == QEvent.FileOpen:
            f = e.file()
            if f:
                self.early_files.append(f)
                self.file_opened.emit(f)
            return True
        return super().event(e)


DragShiftQApplication = SuperDragQApplication
DragShiftApp = SuperDragApp


def mac_setup(qapp):
    # fonts: util.ui_family picks a real installed family. (Substituting the private
    # ".AppleSystemUIFont" made labels draw nothing on macOS 26.)
    try:
        from . import platform_mac
        platform_mac.become_accessory()
    except Exception:
        pass


def send_to_running(payload: dict) -> bool:
    s = QLocalSocket()
    s.connectToServer(IPC_NAME)
    if not s.waitForConnected(300):
        return False
    s.write(json.dumps(payload).encode("utf-8"))
    s.flush()
    s.waitForBytesWritten(500)
    s.disconnectFromServer()
    return True


def setup_logging():
    """Errors go to %LOCALAPPDATA%\\SuperDrag\\log.txt (pythonw / the .exe have no console)."""
    import faulthandler
    if IS_MAC:
        base = Path.home() / "Library" / "Logs" / "SuperDrag"
    else:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "SuperDrag"
    base.mkdir(parents=True, exist_ok=True)
    path = base / "log.txt"
    if path.exists() and path.stat().st_size > 1_000_000:
        path.replace(base / "log.old.txt")
    f = open(path, "a", encoding="utf-8", buffering=1)
    f.write(f"\n==== SuperDrag {VERSION} started {time.strftime('%Y-%m-%d %H:%M:%S')} ====\n")
    if sys.stderr is None or getattr(sys, "frozen", False) or sys.executable.lower().endswith("pythonw.exe"):
        sys.stdout = sys.stderr = f
    faulthandler.enable(f)

    def hook(t, v, tb):
        f.write("Unhandled: " + "".join(traceback.format_exception(t, v, tb)))
    sys.excepthook = hook
    return path


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    try:
        setup_logging()
    except Exception:
        pass
    if IS_WIN:
        try:  # crisp taskbar/tray icon grouping
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SuperDrag.App")
        except Exception:
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = SuperDragQApplication(argv)
    if IS_MAC:
        mac_setup(qapp)
    qapp.setApplicationName(APP_NAME)
    qapp.setApplicationVersion(VERSION)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setWindowIcon(make_icon())

    if "--selftest" in argv:
        return selftest()
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    # already running? hand over and exit (instant: no second UI start-up)
    if send_to_running({"files": files} if files else {"show": "--quiet" not in argv}):
        return 0
    app = SuperDragApp(qapp)
    qapp.file_opened.connect(lambda f: app.queue_files([f]))
    if qapp.early_files:
        app.queue_files(list(qapp.early_files))
    if files:  # e.g. "Send to → SuperDrag" or drag onto the .exe
        QTimer.singleShot(120, lambda: app.queue_files(files))
    elif not app.settings.get("welcomed"):
        QTimer.singleShot(200, app.show_welcome)
    elif "--quiet" not in argv:
        QTimer.singleShot(100, app.open_hub)
    return qapp.exec()


def check_text_renders():
    """Labels must really draw: paint text with the UI fonts and count the inked pixels."""
    from PySide6.QtGui import QImage, QPainter, QColor
    from .util import ui_font, ui_family
    for display in (True, False):
        img = QImage(200, 40, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setFont(ui_font(16, True, display))
        p.setPen(QColor(255, 255, 255))
        p.drawText(img.rect(), Qt.AlignCenter, "WEBP 43.8 KB")
        p.end()
        inked = sum(1 for y in range(0, 40, 2) for x in range(0, 200, 2) if img.pixelColor(x, y).alpha() > 60)
        print(f"font {ui_family(display)!r}: {inked} inked samples")
        if inked < 30:
            raise RuntimeError(f"text does not render with font {ui_family(display)!r}")


def selftest() -> int:
    """Used by CI on the frozen .exe: exercise every library and build the UI, then exit."""
    import tempfile
    from PIL import Image
    try:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "t.png"
            Image.new("RGBA", (64, 48), (255, 100, 80, 255)).save(src)
            for t in convert.targets_for("image", ".png"):
                convert.convert(src, "image", t)
            pdf = convert.convert(src, "image", "PDF")[0]
            for t in convert.PDF_TARGETS:
                convert.convert(pdf, "pdf", t)
            (Path(d) / "n.txt").write_text("hello")
            docx = convert.convert(Path(d) / "n.txt", "text", "DOCX")[0]
            convert.convert(docx, "docx", "TXT")
            imaging.add_background(convert.open_image(src), imaging.Background())
            imaging.compress_pdf(pdf)
            imaging.protect_pdf(pdf, "pw")
            from . import liquid
            liquid.render(Image.new("RGB", (80, 80)), liquid.sdf_circle(80, 80, 40, 40, 30))
            menu = RadialMenu(lambda p: {"Convert": [Item("PNG")]}, lambda p: "1 KB")
            menu._load([str(src)])
            n = lambda *a, **k: None
            for w in (tools.CropWindow(str(src), n), tools.AddBgWindow(str(src), n), tools.EditWindow(str(src), n),
                      tools.AnnotateWindow(str(src), n), tools.RedactWindow(str(src), n),
                      tools.MetadataWindow(str(src), n), tools.CompressWindow([str(src)], n),
                      tools.ResizeWindow([str(src)], n), tools.ProtectWindow(str(pdf), n)):
                w.close()
            ToastStack().info("ok", "ok").dismiss()
            check_text_renders()
        print("SELFTEST OK")
        return 0
    except Exception:
        traceback.print_exc()
        print("SELFTEST FAILED")
        return 1
