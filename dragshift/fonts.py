"""Web and desktop font conversions: TTF ↔ OTF ↔ WOFF ↔ WOFF2.

Enables high-performance conversion between web fonts (WOFF, WOFF2) and desktop typography (TTF, OTF).
"""
from __future__ import annotations

from pathlib import Path

from .util import UserError, sibling

try:
    from fontTools.ttLib import TTFont
    FONTTOOLS_OK = True
except ImportError:  # pragma: no cover
    FONTTOOLS_OK = False

FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
FONT_TARGETS = ["WOFF2", "WOFF", "TTF", "OTF"]


def convert_font(src: str | Path, target: str) -> list[Path]:
    """Convert between TTF, OTF, WOFF, and WOFF2 formats."""
    if not FONTTOOLS_OK:
        raise UserError("fonttools is required for font conversions.")

    src = Path(src)
    tgt = target.upper()

    font = TTFont(str(src))
    out_ext = f".{tgt.lower()}"
    out = sibling(src, ext=out_ext)

    if tgt == "WOFF2":
        font.flavor = "woff2"
    elif tgt == "WOFF":
        font.flavor = "woff"
    elif tgt in ("TTF", "OTF"):
        font.flavor = None
    else:
        raise UserError(f"Unsupported font target format: {target}")

    font.save(str(out))
    return [out]
