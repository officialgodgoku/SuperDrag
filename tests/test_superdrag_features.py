import os
import shutil
import tempfile
from pathlib import Path
import pytest

from dragshift import archive, audio, convert, sheets, subtitles, util, video
from dragshift.actions import copy_paths, copy_files


@pytest.fixture
def temp_dir():
    d = tempfile.mkdtemp(prefix="superdrag_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


def test_archive_compressions_and_extractions(temp_dir):
    # Setup test folder
    src_dir = temp_dir / "my_project"
    src_dir.mkdir()
    (src_dir / "hello.txt").write_text("Hello SuperDrag!", encoding="utf-8")
    (src_dir / "sub").mkdir()
    (src_dir / "sub" / "data.json").write_text('{"app": "SuperDrag"}', encoding="utf-8")

    # 1. Deflate
    out1 = archive.create_archive([src_dir], "ZIP (Deflate)")
    assert len(out1) == 1 and out1[0].exists() and out1[0].suffix == ".zip"

    # 2. Max
    out2 = archive.create_archive([src_dir], "ZIP (Max)")
    assert len(out2) == 1 and out2[0].exists()

    # 3. Store
    out3 = archive.create_archive([src_dir], "ZIP (Store)")
    assert len(out3) == 1 and out3[0].exists()

    # 4. Bzip2
    out4 = archive.create_archive([src_dir], "ZIP (BZIP2)")
    assert len(out4) == 1 and out4[0].exists()

    # 5. LZMA
    out5 = archive.create_archive([src_dir], "ZIP (LZMA)")
    assert len(out5) == 1 and out5[0].exists()

    # 6. Tar.gz
    out6 = archive.create_archive([src_dir], "TAR.GZ")
    assert len(out6) == 1 and out6[0].exists() and out6[0].name.endswith(".tar.gz")

    # 7. Tar
    out7 = archive.create_archive([src_dir], "TAR")
    assert len(out7) == 1 and out7[0].exists() and out7[0].suffix == ".tar"

    # Extract to subfolder
    extracted = archive.extract_archive(out1[0], to_subfolder=True)
    assert len(extracted) == 1
    dest = extracted[0]
    assert dest.is_dir()
    assert (dest / "my_project" / "hello.txt").exists()


def test_subtitles_conversions(temp_dir):
    srt_file = temp_dir / "sub.srt"
    srt_content = """1
00:00:01,000 --> 00:00:04,000
Welcome to SuperDrag!

2
00:00:05,000 --> 00:00:08,000
Drag and drop anything.
"""
    srt_file.write_text(srt_content, encoding="utf-8")

    # 1. SRT -> VTT
    vtt_outs = subtitles.convert_subtitle(srt_file, "VTT")
    assert len(vtt_outs) == 1 and vtt_outs[0].suffix == ".vtt"
    vtt_text = vtt_outs[0].read_text(encoding="utf-8")
    assert "WEBVTT" in vtt_text
    assert "00:00:01.000 --> 00:00:04.000" in vtt_text

    # 2. VTT -> SRT
    srt_outs = subtitles.convert_subtitle(vtt_outs[0], "SRT")
    assert len(srt_outs) == 1 and srt_outs[0].suffix == ".srt"
    re_srt_text = srt_outs[0].read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:04,000" in re_srt_text
    assert "Welcome to SuperDrag!" in re_srt_text

    # 3. Subtitle -> TXT
    txt_outs = subtitles.convert_subtitle(srt_file, "TXT")
    assert len(txt_outs) == 1 and txt_outs[0].suffix == ".txt"
    txt_text = txt_outs[0].read_text(encoding="utf-8")
    assert "Welcome to SuperDrag!" in txt_text
    assert "Drag and drop anything." in txt_text
    assert "-->" not in txt_text


def test_sheets_conversions(temp_dir):
    csv_file = temp_dir / "sample.csv"
    csv_file.write_text("Name,Role,Score\nAlice,Admin,99\nBob,User,85\n", encoding="utf-8")

    # 1. CSV -> TSV
    tsv_outs = sheets.convert_sheet(csv_file, "TSV")
    assert len(tsv_outs) == 1 and tsv_outs[0].suffix == ".tsv"
    tsv_text = tsv_outs[0].read_text(encoding="utf-8")
    assert "Alice\tAdmin\t99" in tsv_text

    # 2. CSV -> XLSX
    xlsx_outs = sheets.convert_sheet(csv_file, "XLSX")
    assert len(xlsx_outs) == 1 and xlsx_outs[0].suffix == ".xlsx"
    assert xlsx_outs[0].stat().st_size > 0

    # 3. CSV -> PDF
    pdf_outs = sheets.convert_sheet(csv_file, "PDF")
    assert len(pdf_outs) == 1 and pdf_outs[0].suffix == ".pdf"
    assert pdf_outs[0].stat().st_size > 0


def test_file_categories():
    assert util.category("video.mp4") == "video"
    assert util.category("clip.avi") == "video"
    assert util.category("song.flac") == "audio"
    assert util.category("track.opus") == "audio"
    assert util.category("movie.srt") == "subtitle"
    assert util.category("finance.xlsx") == "spreadsheet"
    assert util.category("deck.pptx") == "slides"
    assert util.category("archive.zip") == "archive"
    assert util.category("document.pdf") == "pdf"


def test_build_rings_actions_and_tools():
    from dragshift.app import SuperDragApp, Item
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    superdrag = SuperDragApp(app)

    # Test Actions ring on video file
    rings_video = superdrag.build_rings(["C:/fake/video.mp4"])
    assert "Convert" in rings_video
    assert "Tools" in rings_video
    assert "Actions" in rings_video
    action_labels = [it.label for it in rings_video["Actions"]]
    assert "Float" in action_labels
    assert "Copy" in action_labels
    assert "Move" in action_labels
    assert "Copy Path" in action_labels
    assert "Terminal" in action_labels
    assert ("LocalSend" in action_labels) or ("AirDrop" in action_labels)

    # Test Audio file
    rings_audio = superdrag.build_rings(["C:/fake/song.mp3"])
    assert "Convert" in rings_audio
    assert "Tools" in rings_audio
    assert "Actions" in rings_audio
    audio_tool_labels = [it.label for it in rings_audio["Tools"]]
    assert "Normalize" in audio_tool_labels
    assert "Visualize" in audio_tool_labels

    # Test Unsupported file type (should still offer Actions!)
    rings_unknown = superdrag.build_rings(["C:/fake/firmware.bin"])
    assert "Actions" in rings_unknown
    assert len(rings_unknown["Actions"]) == 6

    # Test Image tools ring contains 'Remove BG'
    rings_img = superdrag.build_rings(["C:/fake/photo.jpg"])
    assert "Tools" in rings_img
    img_tool_labels = [it.label for it in rings_img["Tools"]]
    assert "Remove BG" in img_tool_labels
    assert "Add BG" in img_tool_labels


def test_remove_background_feature(temp_dir):
    from PIL import Image, ImageDraw
    from dragshift import imaging

    # 1. Create a synthetic test image with a white background and red subject
    img = Image.new("RGB", (240, 240), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((60, 60, 180, 180), fill=(220, 40, 40))

    src_path = temp_dir / "sample.jpg"
    img.save(src_path, "JPEG")

    # 2. Test auto / AI removal
    out_img = imaging.remove_background(img)
    assert out_img.mode == "RGBA"
    assert out_img.size == (240, 240)

    # 3. Test color mode removal
    p_color = imaging.RemoveBgParams(mode="color", tolerance=30, feather=1)
    out_color = imaging.remove_background(img, p_color)
    assert out_color.mode == "RGBA"
    # Corner should be transparent
    assert out_color.getpixel((5, 5))[3] == 0
    # Subject center should be opaque
    assert out_color.getpixel((120, 120))[3] == 255

    # 4. Test file output
    out_file = imaging.remove_background_file(src_path)
    assert out_file.exists()
    assert out_file.suffix.lower() == ".png"
    assert "No Background" in out_file.name
    with Image.open(out_file) as chk:
        assert chk.mode == "RGBA"

    # 5. Test RemoveBgWindow
    from PySide6.QtWidgets import QApplication
    from dragshift import tools
    import sys

    app = QApplication.instance() or QApplication(sys.argv)
    win = tools.RemoveBgWindow(str(src_path), lambda *a: None)
    assert win.tool_name == "Remove BG"
    win.render()
    win.reset()
    p = win._params()
    assert p.tolerance == 50
    assert p.feather == 2
    assert p.defringe == 1


