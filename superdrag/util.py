"""Shared helpers: output paths, file categories, sizes."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    """Resolve an asset file path, working in both source and PyInstaller environments."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    cand = base / "superdrag" / "assets" / name
    if cand.exists():
        return cand
    cand2 = Path(__file__).resolve().parent / "assets" / name
    if cand2.exists():
        return cand2
    return cand


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".tif", ".tiff",
              ".avif", ".bmp", ".gif", ".ico"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".m4v", ".ts", ".3gp", ".ogv"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".wma"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx", ".doc", ".odt", ".pages", ".rtf"}
TEXT_EXTS = {".txt", ".md", ".log", ".html", ".htm"}
DATA_EXTS = {".json", ".yaml", ".yml", ".toml", ".xml"}
FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
SPREADSHEET_EXTS = {".xlsx", ".ods", ".csv", ".tsv"}
SLIDE_EXTS = {".ppt", ".pptx"}
SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".ssa", ".smi"}
ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z"}
EPUB_EXTS = {".epub", ".mobi", ".fb2"}


def category(path: str | Path) -> str | None:
    p = Path(path)
    if p.is_dir():
        return "folder"
    name_low = p.name.lower()
    if any(name_low.endswith(x) for x in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")):
        return "archive"
    ext = p.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DATA_EXTS:
        return "data"
    if ext in FONT_EXTS:
        return "font"
    if ext in SPREADSHEET_EXTS:
        return "spreadsheet"
    if ext in SLIDE_EXTS:
        return "slides"
    if ext in SUBTITLE_EXTS:
        return "subtitle"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in EPUB_EXTS:
        return "epub"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in TEXT_EXTS:
        return "text"
    return None


def resolve_shortcuts(paths: list[str]) -> list[str]:
    """Windows .lnk shortcuts (desktop icons) stand for the file they point to."""
    if os.name != "nt" or not any(str(p).lower().endswith(".lnk") for p in paths):
        return list(paths)
    out = []
    for p in paths:
        if str(p).lower().endswith(".lnk"):
            try:
                import win32com.client  # type: ignore
                target = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(p)).TargetPath
                if target and os.path.isfile(target):
                    p = target
            except Exception:
                pass
        out.append(p)
    return out


def unique_path(path: str | Path) -> Path:
    """Return `path`, or `name (1).ext`, `name (2).ext`... if it already exists."""
    p = Path(path)
    if not p.exists():
        return p
    i = 1
    while True:
        cand = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not cand.exists():
            return cand
        i += 1


class UserError(Exception):
    """An error with a message that's fine to show the user as-is."""


# Runtime options (filled from Settings at start-up; plain values so worker threads can read them)
CONFIG = {
    "output": "next",        # "next" = beside the original, "folder" = a "SuperDrag" subfolder
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "naming_pattern": "{name}",  # e.g. "{name}_{date}", "{name} {label}"
    "conflict_policy": "rename",  # "rename" = (1), (2); "overwrite" = replace; "skip" = keep
}


def output_dir(src: str | Path) -> Path:
    d = Path(src).parent
    if CONFIG.get("output") == "folder":
        d = d / "SuperDrag"
        d.mkdir(exist_ok=True)
    return d


def resolve_output_path(src: str | Path, suffix_label: str = "", ext: str | None = None,
                        pattern: str | None = None, conflict: str | None = None,
                        extra_tokens: dict[str, str] | None = None) -> Path:
    """Tokenized output path resolver inspired by modern naming engines.

    Tokens supported:
      {name}       Original filename stem (e.g. 'report')
      {ext}        Target extension without dot (e.g. 'webp')
      {label}      Action suffix label (e.g. 'Compressed')
      {date}       Current date (YYYY-MM-DD)
      {time}       Current time (HHMMSS)
      {res}        Resolution if available (e.g. '1920x1080')

    Conflict policies:
      'rename'     Append ' (1)', ' (2)' if destination exists (default)
      'overwrite'  Always write directly to destination
      'skip'       Return target path as-is
    """
    src = Path(src)
    base_dir = output_dir(src)
    pat = pattern or CONFIG.get("naming_pattern") or "{name}"
    conflict_mode = conflict or CONFIG.get("conflict_policy") or "rename"

    target_ext = ext if ext is not None else src.suffix
    if not target_ext.startswith("."):
        target_ext = "." + target_ext

    import datetime
    now = datetime.datetime.now()
    tokens = {
        "name": src.stem,
        "ext": target_ext.lstrip("."),
        "label": suffix_label,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H%M%S"),
        "res": "",
    }
    if extra_tokens:
        tokens.update(extra_tokens)

    formatted_name = pat
    for k, v in tokens.items():
        formatted_name = formatted_name.replace(f"{{{k}}}", str(v))

    if suffix_label and "{label}" not in pat:
        formatted_name = f"{formatted_name} {suffix_label}".strip()

    target_path = base_dir / f"{formatted_name}{target_ext}"

    if conflict_mode == "overwrite" or not target_path.exists():
        return target_path
    if conflict_mode == "rename":
        return unique_path(target_path)
    return target_path


def sibling(src: str | Path, suffix_label: str = "", ext: str | None = None,
            pattern: str | None = None, conflict: str | None = None,
            extra_tokens: dict[str, str] | None = None) -> Path:
    """Output path for `src`. sibling('a.jpg', 'Cropped') -> 'a Cropped.jpg' (never overwrites)."""
    return resolve_output_path(src, suffix_label, ext, pattern, conflict, extra_tokens)


def human_size(n: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def file_size(path: str | Path) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


# ---------------------------------------------------------------- background job lifetime
# QThreadPool runs a QRunnable in C++, but the Python object (and the QObject carrying its
# signals) can be garbage-collected while it's still running: results then never arrive,
# or the app crashes. Keep every job alive until its result has been handled.
ALIVE: set = set()


def keep(job):
    job.setAutoDelete(False)
    ALIVE.add(job)
    return job


def release(job):
    ALIVE.discard(job)


# ---------------------------------------------------------------- fonts
_FONT_FAMILY: dict[bool, str] = {}
_DISPLAY = ["Segoe UI Variable Display", "Segoe UI", "SF Pro Display", "SF Pro", "Helvetica Neue",
            "Inter", "Cantarell", "Noto Sans", "Ubuntu", "DejaVu Sans"]
_TEXT = ["Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "SF Pro", "Helvetica Neue",
         "Inter", "Cantarell", "Noto Sans", "Ubuntu", "DejaVu Sans"]


def ui_family(display: bool = True) -> str:
    """First UI font that is really installed. Never ask Qt for a missing family: on macOS 26
    an unknown family can resolve to a font that draws nothing (labels vanish)."""
    if display not in _FONT_FAMILY:
        from PySide6.QtGui import QFontDatabase
        have = set(QFontDatabase.families())
        pick = next((f for f in (_DISPLAY if display else _TEXT) if f in have), None)
        if pick is None:
            pick = QFontDatabase.systemFont(QFontDatabase.GeneralFont).family()
        _FONT_FAMILY[display] = pick
    return _FONT_FAMILY[display]


def ui_font(px: int = 13, bold: bool = False, display: bool = True):
    from PySide6.QtGui import QFont
    f = QFont(ui_family(display))
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f
