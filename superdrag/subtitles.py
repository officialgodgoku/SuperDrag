"""Subtitle conversions: SRT ↔ VTT ↔ ASS ↔ TXT with time-shifting support.

Inspired by modern subtitle translation and synchronization engines.
Supports SRT (SubRip), VTT (WebVTT), ASS/SSA (Advanced SubStation Alpha),
SAMI (.smi), and plain text dialog extraction.
"""
from __future__ import annotations

import re
from pathlib import Path

from .util import UserError, sibling

SUBTITLE_EXTS = {".srt", ".vtt", ".ass", ".ssa", ".smi"}
SUBTITLE_TARGETS = ["VTT", "SRT", "ASS", "TXT"]


def parse_timestamp(ts: str) -> float:
    """Parse timestamp string (HH:MM:SS.mmm or HH:MM:SS,mmm or H:MM:SS.cc) to seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return float(ts)


def format_srt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms >= 1000:
        s += 1
        ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        s += 1
        cs -= 100
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


def parse_cues(text: str, ext: str) -> list[tuple[float, float, str]]:
    """Parse cues from SRT, VTT, ASS, or SMI text into (start_sec, end_sec, text)."""
    cues = []
    ext = ext.lower()

    if ext in (".ass", ".ssa"):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Dialogue:"):
                # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    start = parse_timestamp(parts[1])
                    end = parse_timestamp(parts[2])
                    txt = parts[9].replace("\\N", "\n").replace("\\n", "\n")
                    txt = re.sub(r"\{[^}]*\}", "", txt).strip()
                    if txt:
                        cues.append((start, end, txt))
        return cues

    if ext == ".smi":
        # SAMI parser: <SYNC Start=1234><P Class=ENCC>Dialog
        syncs = re.findall(r"<SYNC\s+Start=(\d+)>(.*?)(?=(?:<SYNC|\Z))", text, re.IGNORECASE | re.DOTALL)
        for i, (start_ms, body) in enumerate(syncs):
            clean_text = re.sub(r"<[^>]+>", "", body).strip()
            if clean_text and clean_text != "&nbsp;":
                start_sec = int(start_ms) / 1000.0
                end_sec = int(syncs[i + 1][0]) / 1000.0 if i + 1 < len(syncs) else start_sec + 3.0
                cues.append((start_sec, end_sec, clean_text))
        return cues

    # SRT / VTT parser
    # Match pattern: 00:00:01.000 --> 00:00:04.000 (or with commas)
    blocks = re.split(r"\n\s*\n", text.strip())
    time_pat = re.compile(r"(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{2,3})")

    for block in blocks:
        lines = [b.strip() for b in block.splitlines() if b.strip()]
        if not lines:
            continue
        time_match = None
        text_lines = []
        for line in lines:
            m = time_pat.search(line)
            if m:
                time_match = m
            elif time_match is not None:
                text_lines.append(line)
        if time_match:
            start = parse_timestamp(time_match.group(1))
            end = parse_timestamp(time_match.group(2))
            clean_txt = re.sub(r"<[^>]+>", "", "\n".join(text_lines)).strip()
            if clean_txt:
                cues.append((start, end, clean_txt))

    return cues


def render_cues(cues: list[tuple[float, float, str]], target: str) -> str:
    """Render cues to target subtitle format string."""
    tgt = target.upper()

    if tgt == "SRT":
        blocks = []
        for idx, (start, end, txt) in enumerate(cues, 1):
            blocks.append(f"{idx}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{txt}")
        return "\n\n".join(blocks) + "\n"

    if tgt == "VTT":
        blocks = ["WEBVTT\n"]
        for idx, (start, end, txt) in enumerate(cues, 1):
            blocks.append(f"{idx}\n{format_vtt_time(start)} --> {format_vtt_time(end)}\n{txt}")
        return "\n\n".join(blocks) + "\n"

    if tgt in ("ASS", "SSA"):
        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "Collisions: Normal\n"
            "PlayResX: 1920\n"
            "PlayResY: 1080\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )
        dialogues = []
        for start, end, txt in cues:
            ass_txt = txt.replace("\n", "\\N")
            dialogues.append(f"Dialogue: 0,{format_ass_time(start)},{format_ass_time(end)},Default,,0,0,0,,{ass_txt}")
        return header + "\n".join(dialogues) + "\n"

    if tgt == "TXT":
        dialogue = []
        for _, _, txt in cues:
            clean = re.sub(r"<[^>]+>", "", txt).strip()
            if clean and (not dialogue or dialogue[-1] != clean):
                dialogue.append(clean)
        return "\n".join(dialogue) + "\n"

    raise UserError(f"Unsupported subtitle target format: {target}")


def shift_subtitles(src: str | Path, offset_seconds: float) -> Path:
    """Time-shift subtitle events by offset_seconds (e.g. +1.5 or -0.8)."""
    src = Path(src)
    text = src.read_text(encoding="utf-8", errors="replace")
    cues = parse_cues(text, src.suffix)
    shifted = [(max(0.0, s + offset_seconds), max(0.0, e + offset_seconds), txt) for s, e, txt in cues]
    out = sibling(src, f"Shifted {offset_seconds:+.1f}s", src.suffix)
    tgt = "SRT" if src.suffix.lower() == ".srt" else ("VTT" if src.suffix.lower() == ".vtt" else "ASS")
    out.write_text(render_cues(shifted, tgt), encoding="utf-8")
    return out


def convert_subtitle(src: str | Path, target: str) -> list[Path]:
    """Convert subtitles between SRT, VTT, ASS, and TXT formats."""
    src = Path(src)
    tgt = target.upper()
    text = src.read_text(encoding="utf-8", errors="replace")
    cues = parse_cues(text, src.suffix)
    rendered = render_cues(cues, tgt)

    ext_map = {"VTT": ".vtt", "SRT": ".srt", "ASS": ".ass", "SSA": ".ssa", "TXT": ".txt"}
    out = sibling(src, ext=ext_map.get(tgt, f".{tgt.lower()}"))
    out.write_text(rendered, encoding="utf-8")
    return [out]
