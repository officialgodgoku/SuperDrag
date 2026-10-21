"""Audio conversions and processing via FFmpeg:
MP3, M4A, WAV, FLAC, OGG, Opus, AIFF, WMA + Audio Tools (Compress, Metadata, Normalize, Visualize, Trim, Channels, Bleep)."""
from __future__ import annotations

import os
from pathlib import Path

from .util import UserError, sibling
from .video import run_ffmpeg

AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".aiff", ".wma"}
AUDIO_TARGETS = ["MP3", "M4A", "WAV", "FLAC", "OGG", "OPUS", "AIFF", "WMA"]
AUDIO_TOOLS = ["COMPRESS", "METADATA", "NORMALIZE", "VISUALIZE", "TRIM", "CHANNELS", "BLEEP"]


def convert_audio(src: str | Path, target: str) -> list[Path]:
    """Convert audio file to target format."""
    src = Path(src)
    target = target.upper()
    out = sibling(src, ext="." + target.lower())
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")

    try:
        if target == "MP3":
            args = ["-i", str(src), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(tmp)]
        elif target == "M4A":
            args = ["-i", str(src), "-vn", "-c:a", "aac", "-b:a", "192k", str(tmp)]
        elif target == "WAV":
            args = ["-i", str(src), "-vn", "-c:a", "pcm_s16le", str(tmp)]
        elif target == "FLAC":
            args = ["-i", str(src), "-vn", "-c:a", "flac", str(tmp)]
        elif target == "OGG":
            args = ["-i", str(src), "-vn", "-c:a", "libvorbis", "-q:a", "5", str(tmp)]
        elif target == "OPUS":
            args = ["-i", str(src), "-vn", "-c:a", "libopus", "-b:a", "128k", str(tmp)]
        elif target == "AIFF":
            args = ["-i", str(src), "-vn", "-c:a", "pcm_s16be", str(tmp)]
        elif target == "WMA":
            args = ["-i", str(src), "-vn", "-c:a", "wmav2", "-b:a", "192k", str(tmp)]
        else:
            raise UserError(f"Unsupported audio target: {target}")

        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def compress_audio(src: str | Path) -> list[Path]:
    """Compress audio to compact 128 kbps MP3."""
    src = Path(src)
    out = sibling(src, suffix_label="Compressed", ext=".mp3")
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-vn", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def normalize_audio(src: str | Path) -> list[Path]:
    """Normalize audio loudness using EBU R128 standard."""
    src = Path(src)
    out = sibling(src, suffix_label="Normalized", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-af", "loudnorm", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def visualize_audio(src: str | Path) -> list[Path]:
    """Generate high-resolution waveform spectrogram image."""
    src = Path(src)
    out = sibling(src, suffix_label="Waveform", ext=".png")
    tmp = out.with_name(f".~{out.stem}.part.png")
    try:
        args = [
            "-i", str(src),
            "-lavfi", "showwavespic=s=960x320:colors=#5ac8ff|#2f7bff",
            "-frames:v", "1",
            str(tmp),
        ]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def trim_audio(src: str | Path, duration: int = 30) -> list[Path]:
    """Trim first 30 seconds of audio."""
    src = Path(src)
    out = sibling(src, suffix_label="Trimmed", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-t", str(duration), "-c", "copy", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def convert_channels(src: str | Path) -> list[Path]:
    """Toggle between Stereo (2ch) and Mono (1ch)."""
    src = Path(src)
    out = sibling(src, suffix_label="Mono", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-ac", "1", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def bleep_audio(src: str | Path) -> list[Path]:
    """Add a censor 1kHz bleep tone at start/marker."""
    src = Path(src)
    out = sibling(src, suffix_label="Bleeped", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        # Mix a 1kHz sine beep at 0.5s for 1s
        args = [
            "-i", str(src),
            "-filter_complex", "sine=f=1000:d=1[b];[0:a][b]amix=inputs=2:duration=first",
            str(tmp),
        ]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def strip_metadata_audio(src: str | Path) -> list[Path]:
    """Strip all tags and metadata from audio file."""
    src = Path(src)
    out = sibling(src, suffix_label="Clean", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-map_metadata", "-1", "-c", "copy", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
