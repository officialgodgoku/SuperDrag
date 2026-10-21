"""Tests for video conversion and tooling support."""
from pathlib import Path
import pytest
from PIL import Image

from dragshift import convert, video
from dragshift.util import category


@pytest.fixture(scope="session")
def sample_video(tmp_path_factory) -> Path:
    tmp_path = tmp_path_factory.mktemp("video_test")
    p = tmp_path / "clip.mp4"
    video.run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-c:v", "libx264", "-c:a", "aac",
        str(p),
    ])
    assert p.exists() and p.stat().st_size > 0
    return p


def test_video_categories():
    for ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".m4v"):
        assert category(f"test{ext}") == "video"


def test_video_targets():
    targets = convert.targets_for("video", ".mp4")
    assert "MP4" not in targets
    assert "GIF" in targets
    assert "WEBM" in targets
    assert "MP3" in targets
    assert "MOV" in targets


def test_video_dims(sample_video):
    dims = video.get_video_dims(sample_video)
    assert dims == (320, 240)


def test_convert_to_gif(sample_video):
    outs = convert.convert(sample_video, "video", "GIF")
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert out.suffix.lower() == ".gif"
    with Image.open(out) as im:
        assert im.format == "GIF"


def test_convert_to_mp3(sample_video):
    outs = convert.convert(sample_video, "video", "MP3")
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert out.suffix.lower() == ".mp3"


def test_convert_to_webm(sample_video):
    outs = convert.convert(sample_video, "video", "WEBM")
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert out.suffix.lower() == ".webm"


def test_video_mute(sample_video):
    outs = video.mute_video(sample_video)
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert "Muted" in out.name


def test_video_compress(sample_video):
    outs = video.compress_video(sample_video)
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert "Compressed" in out.name


def test_convert_to_mov(sample_video):
    outs = convert.convert(sample_video, "video", "MOV")
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert out.suffix.lower() == ".mov"


def test_convert_to_mkv(sample_video):
    outs = convert.convert(sample_video, "video", "MKV")
    assert len(outs) == 1
    out = outs[0]
    assert out.exists() and out.stat().st_size > 0
    assert out.suffix.lower() == ".mkv"


def test_gif_to_mp4(sample_video):
    gif = convert.convert(sample_video, "video", "GIF")[0]
    assert gif.suffix.lower() == ".gif"
    mp4 = convert.convert(gif, "image", "MP4")[0]
    assert mp4.exists() and mp4.stat().st_size > 0
    assert mp4.suffix.lower() == ".mp4"

