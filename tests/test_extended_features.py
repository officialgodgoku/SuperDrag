"""Tests for extended SuperDrag features:
- Structured Data conversions: JSON ↔ YAML ↔ TOML ↔ XML ↔ CSV
- Web Font conversions: TTF ↔ WOFF ↔ WOFF2 ↔ OTF
- Bitmap-to-SVG vector tracing
- Advanced subtitles: ASS/SSA, SAMI, and time shifting
- Web & clipboard SourceFetcher
- Tokenized output naming and conflict resolution policies
- Headless CLI execution
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from superdrag import cli, convert, data, fetcher, fonts, imaging, subtitles, util


def test_data_conversions(tmp_path: Path):
    """Test full circular and cross-format transcoding of structured data."""
    # 1. JSON source
    json_path = tmp_path / "config.json"
    raw_dict = {
        "app": "SuperDrag",
        "version": 2,
        "active": True,
        "items": [1, 2, 3],
        "meta": {"author": "Manish", "offline": True},
    }
    json_path.write_text(json.dumps(raw_dict), encoding="utf-8")

    # Test category
    assert util.category(json_path) == "data"
    targets = convert.targets_for("data", ".json")
    for expected in ["YAML", "TOML", "XML", "CSV"]:
        assert expected in targets

    # Convert to YAML
    yaml_outs = convert.convert(json_path, "data", "YAML")
    assert len(yaml_outs) == 1
    assert yaml_outs[0].exists()
    yaml_content = yaml_outs[0].read_text(encoding="utf-8")
    assert "SuperDrag" in yaml_content
    assert "Manish" in yaml_content

    # Convert to TOML
    toml_outs = convert.convert(json_path, "data", "TOML")
    assert len(toml_outs) == 1
    assert toml_outs[0].exists()
    toml_content = toml_outs[0].read_text(encoding="utf-8")
    assert "SuperDrag" in toml_content

    # Convert to XML
    xml_outs = convert.convert(json_path, "data", "XML")
    assert len(xml_outs) == 1
    assert xml_outs[0].exists()
    xml_content = xml_outs[0].read_text(encoding="utf-8")
    assert "<app>SuperDrag</app>" in xml_content

    # Convert to CSV
    csv_outs = convert.convert(json_path, "data", "CSV")
    assert len(csv_outs) == 1
    assert csv_outs[0].exists()

    # Convert YAML back to JSON
    json_back = convert.convert(yaml_outs[0], "data", "JSON")
    assert len(json_back) == 1
    reloaded = json.loads(json_back[0].read_text(encoding="utf-8"))
    assert reloaded["app"] == "SuperDrag"
    assert reloaded["version"] == 2


def test_font_conversions(tmp_path: Path):
    """Test TTF ↔ WOFF ↔ WOFF2 font conversions."""
    system_font = Path(r"C:\Windows\Fonts\arial.ttf")
    if not system_font.exists():
        pytest.skip("arial.ttf not available on system")

    # Copy font to tmp_path to avoid writing into C:\Windows\Fonts
    src_font = tmp_path / "custom.ttf"
    src_font.write_bytes(system_font.read_bytes())

    # Category check
    assert util.category(src_font) == "font"
    targets = convert.targets_for("font", ".ttf")
    assert "WOFF" in targets
    assert "WOFF2" in targets

    # Convert TTF -> WOFF
    woff_outs = convert.convert(src_font, "font", "WOFF")
    assert len(woff_outs) == 1
    assert woff_outs[0].exists()
    assert woff_outs[0].stat().st_size > 0

    # Convert TTF -> WOFF2
    woff2_outs = convert.convert(src_font, "font", "WOFF2")
    assert len(woff2_outs) == 1
    assert woff2_outs[0].exists()
    assert woff2_outs[0].stat().st_size > 0
    # WOFF2 is significantly smaller than WOFF
    assert woff2_outs[0].stat().st_size < woff_outs[0].stat().st_size

    # Convert WOFF back to TTF
    ttf_back = convert.convert(woff_outs[0], "font", "TTF")
    assert len(ttf_back) == 1
    assert ttf_back[0].exists()
    assert ttf_back[0].stat().st_size > 0


def test_vector_tracing(tmp_path: Path):
    """Test bitmap to SVG vector tracing."""
    img_path = tmp_path / "icon.png"
    im = Image.new("RGB", (64, 64), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse([16, 16, 48, 48], fill=(220, 20, 60))
    im.save(img_path)

    # 1. Via imaging function directly
    svg_out = imaging.trace_bitmap_to_svg(img_path, max_colors=4)
    assert svg_out.exists()
    svg_text = svg_out.read_text(encoding="utf-8")
    assert "<svg" in svg_text
    assert "xmlns=" in svg_text
    assert "<path" in svg_text
    assert "fill=" in svg_text

    # 2. Via convert dispatch table
    assert "SVG" in convert.targets_for("image", ".png")
    svg_outs = convert.convert(img_path, "image", "SVG")
    assert len(svg_outs) == 1
    assert svg_outs[0].exists()


def test_subtitles_advanced(tmp_path: Path):
    """Test ASS/SSA, SAMI, and time shifting in subtitles."""
    srt_path = tmp_path / "sample.srt"
    srt_path.write_text(
        "1\n00:00:01,000 --> 00:00:04,500\nHello, world!\n\n2\n00:00:05,000 --> 00:00:08,200\nSecond subtitle.\n",
        encoding="utf-8",
    )

    # Convert to ASS
    ass_outs = subtitles.convert_subtitle(srt_path, "ASS")
    assert len(ass_outs) == 1
    assert ass_outs[0].exists()
    ass_content = ass_outs[0].read_text(encoding="utf-8")
    assert "[Script Info]" in ass_content
    assert "[Events]" in ass_content
    assert "Dialogue: 0,0:00:01.00,0:00:04.50" in ass_content
    assert "Hello, world!" in ass_content

    # Convert ASS to VTT
    vtt_outs = subtitles.convert_subtitle(ass_outs[0], "VTT")
    assert len(vtt_outs) == 1
    vtt_content = vtt_outs[0].read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_content
    assert "00:00:01.000 --> 00:00:04.500" in vtt_content

    # Time shift (+2.0 seconds)
    shifted = subtitles.shift_subtitles(srt_path, 2.0)
    assert shifted.exists()
    shifted_content = shifted.read_text(encoding="utf-8")
    assert "00:00:03,000 --> 00:00:06,500" in shifted_content


def test_source_fetcher(tmp_path: Path):
    """Test Data URI parsing and source extraction from mime data."""
    # 1. Data URI decoding
    data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    parsed = fetcher.parse_data_uri(data_uri)
    assert parsed is not None
    bytes_data, ext = parsed
    assert ext == ".png"
    assert len(bytes_data) > 0

    # Test fetch_url with data URI
    saved_path = fetcher.fetch_url(data_uri)
    assert saved_path is not None
    assert saved_path.exists()
    assert saved_path.suffix == ".png"

    # 2. Mock QMimeData object
    class DummyMime:
        def urls(self):
            return []

        def hasUrls(self):
            return False

        def hasImage(self):
            return False

        def hasHtml(self):
            return True

        def html(self):
            return f'<p>Dropped from webpage <img src="{data_uri}"></p>'

        def hasText(self):
            return False

    sources = fetcher.extract_sources_from_mimedata(DummyMime())
    assert len(sources) == 1
    assert Path(sources[0]).exists()


def test_tokenized_naming_and_conflicts(tmp_path: Path):
    """Test OutputPathResolver pattern substitution and collision policies."""
    src = tmp_path / "photo.jpg"
    src.write_bytes(b"dummy")

    # 1. Default rename conflict policy
    p1 = util.resolve_output_path(src, ext=".webp", pattern="{name}", conflict="rename")
    p1.write_bytes(b"webp1")
    p2 = util.resolve_output_path(src, ext=".webp", pattern="{name}", conflict="rename")
    assert p2.name == "photo (1).webp"

    # 2. Overwrite conflict policy
    p_over = util.resolve_output_path(src, ext=".webp", pattern="{name}", conflict="overwrite")
    assert p_over.name == "photo.webp"

    # 3. Token substitution with date and custom token
    p_custom = util.resolve_output_path(
        src,
        ext=".png",
        pattern="{name}_{date}_{res}",
        conflict="overwrite",
        extra_tokens={"res": "1920x1080"},
    )
    assert "photo_" in p_custom.name
    assert "_1920x1080.png" in p_custom.name


def test_cli_subcommands(tmp_path: Path):
    """Test CLI execution of info, convert, and vectorize."""
    sample = tmp_path / "data.json"
    sample.write_text('{"cli": true}', encoding="utf-8")

    # Test info
    assert cli.run_cli(["superdrag", "info", str(sample)]) == 0

    # Test convert
    assert cli.run_cli(["superdrag", "convert", str(sample), "--to", "YAML"]) == 0
    assert (tmp_path / "data.yaml").exists()

    # Test vectorize
    img_sample = tmp_path / "dot.png"
    Image.new("RGB", (20, 20), (100, 150, 200)).save(img_sample)
    assert cli.run_cli(["superdrag", "vectorize", str(img_sample)]) == 0
    assert (tmp_path / "dot.svg").exists()
