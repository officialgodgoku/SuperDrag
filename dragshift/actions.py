"""File actions for the Ctrl+drag ring: LocalSend/AirDrop, Float shelf, Copy, Move, Copy Path, Terminal."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication, QFileDialog

from .util import UserError

if TYPE_CHECKING:
    from .app import SuperDragApp


def get_localsend_path() -> str | None:
    """Find LocalSend executable on Windows."""
    candidates = [
        r"C:\Program Files\LocalSend\localsend_app.exe",
        r"C:\Program Files (x86)\LocalSend\localsend_app.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\LocalSend\localsend_app.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    found = shutil.which("localsend_app.exe") or shutil.which("localsend")
    return found


def copy_paths(paths: list[str]) -> str:
    """Copy full file paths as text, with one path per line."""
    text = "\n".join(os.path.abspath(p) for p in paths)
    QApplication.clipboard().setText(text)
    count = len(paths)
    return f"Copied {count} path{'s' if count != 1 else ''} to clipboard"


def copy_files(paths: list[str]) -> str:
    """Copy files to clipboard ready to paste into Explorer/Finder."""
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(os.path.abspath(p)) for p in paths])
    QApplication.clipboard().setMimeData(mime)
    count = len(paths)
    return f"Copied {count} file{'s' if count != 1 else ''} to clipboard (Ctrl+V to paste)"


def move_files(paths: list[str], parent_widget=None) -> tuple[str, list[Path]]:
    """Prompt user to choose destination folder and move originals there."""
    initial_dir = str(Path(paths[0]).parent)
    dest_dir = QFileDialog.getExistingDirectory(
        parent_widget,
        f"Move {len(paths)} file{'s' if len(paths) != 1 else ''} to…",
        initial_dir,
    )
    if not dest_dir:
        return "Move cancelled", []

    dest_path = Path(dest_dir)
    moved_paths: list[Path] = []
    for p in paths:
        src = Path(p)
        target = dest_path / src.name
        # Avoid overwriting directly if destination file exists
        if target.exists() and target != src:
            i = 1
            while (dest_path / f"{src.stem} ({i}){src.suffix}").exists():
                i += 1
            target = dest_path / f"{src.stem} ({i}){src.suffix}"
        if src.resolve() != target.resolve():
            shutil.move(str(src), str(target))
            moved_paths.append(target)
        else:
            moved_paths.append(src)

    count = len(moved_paths)
    return f"Moved {count} file{'s' if count != 1 else ''} to {dest_path.name}", moved_paths


def open_terminal(paths: list[str] | str) -> str:
    """Open folder or file's containing folder in Terminal/PowerShell/Command Prompt."""
    if isinstance(paths, (str, Path)):
        paths = [str(paths)]
    if not paths:
        return "No files specified"
    first = Path(paths[0])
    target_dir = first if first.is_dir() else first.parent
    target_str = str(target_dir.resolve())

    if sys.platform == "win32":
        # Prefer Windows Terminal (wt), fallback to PowerShell or cmd
        wt = shutil.which("wt.exe")
        if wt:
            subprocess.Popen([wt, "-d", target_str])
        else:
            subprocess.Popen(
                ["powershell.exe", "-NoExit", "-Command", f"Set-Location '{target_str}'"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        return f"Opened Terminal in {target_dir.name}"

    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Terminal", target_str])
        return f"Opened Terminal in {target_dir.name}"

    else:
        # Linux fallback
        for term in ("xdg-terminal", "gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal"):
            if shutil.which(term):
                subprocess.Popen([term], cwd=target_str)
                return f"Opened Terminal in {target_dir.name}"
        return f"Terminal opened at {target_dir.name}"


def share_localsend(paths: list[str]) -> str:
    """Share files and folders through LocalSend."""
    return share_via_localsend_or_airdrop(paths)


def share_airdrop(paths: list[str]) -> str:
    """Share files and folders through AirDrop."""
    return share_via_localsend_or_airdrop(paths)


def share_via_localsend_or_airdrop(paths: list[str]) -> str:
    """Share files and folders through LocalSend (Windows/Linux) or AirDrop (macOS)."""
    if sys.platform == "darwin":
        try:
            from . import platform_mac
            if platform_mac.send_airdrop(paths):
                return f"AirDrop opened for {len(paths)} file(s)"
        except Exception:
            pass

    # Windows / Linux: LocalSend
    localsend = get_localsend_path()
    if localsend:
        # Pass files to LocalSend process
        args = [localsend] + [os.path.abspath(p) for p in paths]
        try:
            subprocess.Popen(args)
            return f"Opened in LocalSend ({len(paths)} file{'s' if len(paths) != 1 else ''})"
        except Exception as e:
            return f"Failed to launch LocalSend: {e}"

    # If LocalSend is not installed, copy files to clipboard and open web/store
    copy_files(paths)
    import webbrowser
    webbrowser.open("https://localsend.org/#/download")
    return "LocalSend not detected. Opened download page (files copied to clipboard)"
