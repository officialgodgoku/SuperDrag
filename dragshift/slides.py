"""Presentation slide conversions: PPT / PPTX → PDF, JPG, PNG."""
from __future__ import annotations

import sys
from pathlib import Path

from .util import UserError, sibling

SLIDE_EXTS = {".ppt", ".pptx"}
SLIDE_TARGETS = ["PDF", "JPG", "PNG"]


def ppt_to_pdf(src: Path, out: Path) -> bool:
    """Use Microsoft PowerPoint COM automation if installed on Windows."""
    if sys.platform != "win32":
        return False
    try:
        import win32com.client
        ppt = win32com.client.DispatchEx("PowerPoint.Application")
        try:
            pres = ppt.Presentations.Open(str(src.resolve()), ReadOnly=True, Untitled=False, WithWindow=False)
            pres.SaveAs(str(out.resolve()), 32)  # ppSaveAsPDF = 32
            pres.Close()
            return out.exists() and out.stat().st_size > 0
        finally:
            ppt.Quit()
    except Exception:
        return False


def convert_slides(src: str | Path, target: str) -> list[Path]:
    src = Path(src)
    target = target.upper()
    pdf_out = sibling(src, ext=".pdf")

    # 1. Convert to PDF first
    if not ppt_to_pdf(src, pdf_out):
        # Fallback: extract embedded slide images / text via PyMuPDF or zipfile
        import zipfile
        from . import convert
        try:
            with zipfile.ZipFile(src) as zf:
                # Look for media images
                media = [n for n in zf.namelist() if n.startswith("ppt/media/")]
                if media:
                    imgs = []
                    for m in media:
                        data = zf.read(m)
                        from PIL import Image
                        import io
                        im = Image.open(io.BytesIO(data))
                        imgs.append(convert.flatten(im))
                    if imgs:
                        imgs[0].save(pdf_out, "PDF", resolution=150.0, save_all=True, append_images=imgs[1:])
        except Exception:
            pass

    if not pdf_out.exists() or pdf_out.stat().st_size == 0:
        raise UserError(f"Could not convert presentation {src.name} to {target}. Make sure Microsoft PowerPoint is installed.")

    if target == "PDF":
        return [pdf_out]
    elif target in ("JPG", "PNG"):
        from . import convert
        imgs = convert.pdf_to_images(pdf_out, target)
        # remove intermediate PDF if user only wanted images
        if pdf_out.exists():
            try:
                pdf_out.unlink()
            except OSError:
                pass
        return imgs
    else:
        raise UserError(f"Unsupported slide conversion target: {target}")
