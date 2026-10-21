"""Subtitle conversions: SRT ↔ VTT."""
from __future__ import annotations

import re
from pathlib import Path

from .util import UserError, sibling

SUBTITLE_EXTS = {".srt", ".vtt"}
SUBTITLE_TARGETS = ["VTT", "SRT", "TXT"]


def srt_to_vtt(src: str | Path) -> list[Path]:
    src = Path(src)
    text = src.read_text(encoding="utf-8", errors="replace")
    # Convert timestamps: 00:00:20,000 --> 00:00:24,400 to 00:00:20.000 --> 00:00:24.400
    vtt_text = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
    vtt_content = "WEBVTT\n\n" + vtt_text.lstrip()
    out = sibling(src, ext=".vtt")
    out.write_text(vtt_content, encoding="utf-8")
    return [out]


def vtt_to_srt(src: str | Path) -> list[Path]:
    src = Path(src)
    raw = src.read_text(encoding="utf-8", errors="replace")
    # Strip WEBVTT header and any NOTE/STYLE blocks
    lines = raw.splitlines()
    body_lines = []
    skip = True
    for line in lines:
        if skip:
            if "-->" in line:
                skip = False
                body_lines.append(line)
            continue
        body_lines.append(line)

    text = "\n".join(body_lines)
    # Convert timestamps: 00:00:20.000 --> 00:00:24.400 to 00:00:20,000 --> 00:00:24,400
    srt_text = re.sub(r"(\d{2}:\d{2}:\d{2})\.(\d{3})", r"\1,\2", text)

    # Ensure sequential numbering if missing
    blocks = srt_text.strip().split("\n\n")
    formatted_blocks = []
    for idx, block in enumerate(blocks, 1):
        lines = [b.strip() for b in block.splitlines() if b.strip()]
        if not lines:
            continue
        if not lines[0].isdigit():
            formatted_blocks.append(f"{idx}\n" + "\n".join(lines))
        else:
            formatted_blocks.append("\n".join(lines))

    out = sibling(src, ext=".srt")
    out.write_text("\n\n".join(formatted_blocks) + "\n", encoding="utf-8")
    return [out]


def subtitle_to_txt(src: str | Path) -> list[Path]:
    """Extract clean dialogue text without timestamps."""
    src = Path(src)
    lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
    dialogue = []
    for line in lines:
        s = line.strip()
        if not s or s.isdigit() or "-->" in s or s.startswith("WEBVTT") or s.startswith("NOTE"):
            continue
        clean = re.sub(r"<[^>]+>", "", s)
        if clean and (not dialogue or dialogue[-1] != clean):
            dialogue.append(clean)
    out = sibling(src, ext=".txt")
    out.write_text("\n".join(dialogue) + "\n", encoding="utf-8")
    return [out]


def convert_subtitle(src: str | Path, target: str) -> list[Path]:
    target = target.upper()
    if target == "VTT":
        return srt_to_vtt(src)
    if target == "SRT":
        return vtt_to_srt(src)
    if target == "TXT":
        return subtitle_to_txt(src)
    raise UserError(f"Unsupported subtitle conversion target: {target}")
