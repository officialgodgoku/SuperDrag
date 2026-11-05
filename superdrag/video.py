"""Video processing: conversions, compression, audio extraction, muting, and video tools via FFmpeg."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .util import UserError, sibling

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".m4v", ".ts", ".3gp", ".ogv"}
VIDEO_TARGETS = ["MP4", "MKV", "WEBM", "AVI", "WMV", "GIF", "MP3", "MOV", "WAV"]
VIDEO_TOOLS = ["COMPRESS", "METADATA", "MUTE", "TRIM", "CROP", "SPEED", "SNAPSHOT", "SPLIT", "REDACT"]


def get_ffmpeg() -> str:
    """Find ffmpeg binary from PATH, imageio_ffmpeg, or local application path."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    base_dirs = [Path(sys.executable).parent, Path(__file__).resolve().parent.parent]
    for b in base_dirs:
        cand = b / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if cand.is_file():
            return str(cand)

    raise UserError(
        "FFmpeg is required for video operations. "
        "Install ffmpeg (e.g. winget install Gyan.FFmpeg) or imageio-ffmpeg."
    )


def run_ffmpeg(args: list[str]) -> subprocess.CompletedProcess:
    ffmpeg = get_ffmpeg()
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    if res.returncode != 0:
        err = res.stderr.strip() or f"FFmpeg failed with exit code {res.returncode}"
        raise UserError(f"Video operation failed: {err}")
    return res


def get_video_dims(path: str | Path) -> tuple[int, int] | None:
    """Extract (width, height) using ffmpeg probe."""
    try:
        ffmpeg = get_ffmpeg()
        cmd = [ffmpeg, "-hide_banner", "-i", str(path)]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        match = re.search(r",\s*(\d{2,5})x(\d{2,5})", res.stderr)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return None


_DETECTED_HW: str | None = None


def detect_hardware_encoder() -> str:
    """Probe for functional hardware encoder: QSV (Intel), NVENC (NVIDIA), AMF (AMD)."""
    global _DETECTED_HW
    if _DETECTED_HW is not None:
        return _DETECTED_HW

    try:
        ffmpeg = get_ffmpeg()
    except Exception:
        _DETECTED_HW = "cpu"
        return _DETECTED_HW

    # Probe order: QSV, NVENC, AMF
    for enc in ("h264_qsv", "h264_nvenc", "h264_amf"):
        try:
            res = subprocess.run(
                [
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
                    "-c:v", enc, "-frames:v", "1", "-f", "null", "-",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
                timeout=3,
            )
            if res.returncode == 0:
                _DETECTED_HW = enc.replace("h264_", "")
                return _DETECTED_HW
        except Exception:
            pass

    _DETECTED_HW = "cpu"
    return _DETECTED_HW


def get_h264_encoder_args(crf: int = 28) -> list[str]:
    """Return encoder arguments based on user's Settings (Hardware Acceleration and Preset)."""
    from .util import CONFIG
    accel = CONFIG.get("hw_accel", "off")
    preset = CONFIG.get("video_preset", "veryfast")

    chosen = accel
    if accel == "auto":
        chosen = detect_hardware_encoder()

    if chosen == "qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf), "-pix_fmt", "nv12"]
    elif chosen == "nvenc":
        return ["-c:v", "h264_nvenc", "-cq", str(crf), "-preset", "p4", "-pix_fmt", "yuv420p"]
    elif chosen == "amf":
        return ["-c:v", "h264_amf", "-rc", "cqp", "-qp_i", str(crf), "-qp_p", str(crf), "-pix_fmt", "yuv420p"]

    # CPU fallback with user-selected speed preset
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]


def convert_video(src: str | Path, target: str) -> list[Path]:
    """Convert video source to target format."""
    src = Path(src)
    target = target.upper()
    out = sibling(src, ext="." + target.lower())
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")

    try:
        if target == "MP4":
            enc_args = get_h264_encoder_args(crf=23)
            args = [
                "-i", str(src),
            ] + enc_args + [
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                str(tmp),
            ]
        elif target == "WEBM":
            args = [
                "-i", str(src),
                "-c:v", "libvpx-vp9",
                "-crf", "32",
                "-b:v", "0",
                "-c:a", "libopus",
                "-b:a", "96k",
                str(tmp),
            ]
        elif target == "MOV":
            args = [
                "-i", str(src),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                str(tmp),
            ]
        elif target == "MKV":
            args = [
                "-i", str(src),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                str(tmp),
            ]
        elif target == "AVI":
            args = [
                "-i", str(src),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "mp3",
                str(tmp),
            ]
        elif target == "WMV":
            args = [
                "-i", str(src),
                "-c:v", "wmv2",
                "-b:v", "2M",
                "-c:a", "wmav2",
                "-b:a", "128k",
                str(tmp),
            ]
        elif target == "GIF":
            vf = (
                "fps=15,scale='min(480,iw)':-2:flags=lanczos,"
                "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer"
            )
            args = [
                "-i", str(src),
                "-vf", vf,
                "-loop", "0",
                str(tmp),
            ]
        elif target == "MP3":
            args = [
                "-i", str(src),
                "-vn",
                "-c:a", "libmp3lame",
                "-q:a", "2",
                str(tmp),
            ]
        elif target == "WAV":
            args = [
                "-i", str(src),
                "-vn",
                "-c:a", "pcm_s16le",
                str(tmp),
            ]
        else:
            raise UserError(f"Unsupported video target format: {target}")

        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def mute_video(src: str | Path) -> list[Path]:
    """Strip audio from video."""
    src = Path(src)
    out = sibling(src, suffix_label="Muted", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-i", str(src), "-c:v", "copy", "-an", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def compress_video(src: str | Path, crf: int = 28) -> list[Path]:
    """Compress video using H.264 with hardware acceleration if enabled in Settings,
    falling back smoothly to CPU."""
    src = Path(src)
    out = sibling(src, suffix_label="Compressed", ext=".mp4")
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")

    enc_args = get_h264_encoder_args(crf=crf)
    try:
        args = ["-i", str(src)] + enc_args + [
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(tmp),
        ]
        try:
            run_ffmpeg(args)
        except UserError:
            # If a hardware encoder failed for any reason, retry with CPU libx264
            if "-c:v" in enc_args and enc_args[enc_args.index("-c:v") + 1] != "libx264":
                cpu_args = ["-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)]
                run_ffmpeg(cpu_args)
            else:
                raise
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def take_snapshot(src: str | Path, time_sec: float = 1.0) -> list[Path]:
    """Extract a high-resolution frame snapshot from the video as PNG."""
    src = Path(src)
    out = sibling(src, suffix_label="Snapshot", ext=".png")
    tmp = out.with_name(f".~{out.stem}.part.png")
    try:
        args = ["-ss", str(time_sec), "-i", str(src), "-vframes", "1", "-q:v", "2", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def change_speed(src: str | Path, speed: float = 2.0) -> list[Path]:
    """Speed up or slow down video (default: 2x)."""
    src = Path(src)
    out = sibling(src, suffix_label=f"{speed}x", ext=".mp4")
    tmp = out.with_name(f".~{out.stem}.part.mp4")
    try:
        pts = 1.0 / speed
        args = [
            "-i", str(src),
            "-filter_complex", f"[0:v]setpts={pts}*PTS[v];[0:a]atempo={speed}[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac",
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


def trim_video(src: str | Path, duration: int = 30) -> list[Path]:
    """Trim first 30 seconds of video."""
    src = Path(src)
    out = sibling(src, suffix_label="Trimmed", ext=src.suffix)
    tmp = out.with_name(f".~{out.stem}.part{out.suffix}")
    try:
        args = ["-ss", "00:00:00", "-i", str(src), "-t", str(duration), "-c", "copy", str(tmp)]
        run_ffmpeg(args)
        os.replace(tmp, out)
        return [out]
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def strip_metadata_video(src: str | Path) -> list[Path]:
    """Strip all metadata and GPS tags from video."""
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


def split_video(src: str | Path, segment_time: int = 60) -> list[Path]:
    """Split video into 60s segments."""
    src = Path(src)
    out_pattern = sibling(src, suffix_label="part_%03d", ext=src.suffix)
    args = [
        "-i", str(src),
        "-c", "copy",
        "-map", "0",
        "-segment_time", str(segment_time),
        "-f", "segment",
        "-reset_timestamps", "1",
        str(out_pattern),
    ]
    run_ffmpeg(args)
    # Find generated segments
    parent = out_pattern.parent
    stem_prefix = src.stem + " part_"
    return sorted(p for p in parent.iterdir() if p.name.startswith(stem_prefix))


def crop_video(src: str | Path) -> list[Path]:
    """Center square crop 1:1 for social / avatars."""
    src = Path(src)
    out = sibling(src, suffix_label="Cropped", ext=".mp4")
    tmp = out.with_name(f".~{out.stem}.part.mp4")
    try:
        args = [
            "-i", str(src),
            "-vf", "crop='min(iw,ih)':'min(iw,ih)'",
            "-c:v", "libx264", "-c:a", "copy",
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
