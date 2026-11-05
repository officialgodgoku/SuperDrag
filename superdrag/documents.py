"""Extended document, EPUB, and Markdown conversions."""
from __future__ import annotations

import html
import io
import os
import zipfile
from pathlib import Path

import pymupdf as fitz
from docx import Document

from .util import UserError, sibling

DOC_EXTS = {".docx", ".doc", ".odt", ".pages", ".rtf"}
EPUB_EXTS = {".epub", ".mobi", ".fb2"}


def create_epub(title: str, body_html: str, out_path: Path) -> None:
    """Pack HTML content into a clean, compliant EPUB file."""
    tmp = out_path.with_name(f".~{out_path.stem}.part.epub")
    try:
        with zipfile.ZipFile(tmp, "w") as zf:
            # 1. mimetype (must be first, uncompressed)
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. container.xml
            container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""
            zf.writestr("META-INF/container.xml", container_xml)

            # 3. Chapter HTML
            chapter_html = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>{html.escape(title)}</title>
  <style>body {{ font-family: sans-serif; line-height: 1.5; margin: 5%; }}</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  {body_html}
</body>
</html>"""
            zf.writestr("OEBPS/chapter.xhtml", chapter_html)

            # 4. content.opf
            content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="pub-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">urn:uuid:superdrag-{out_path.stem}</dc:identifier>
    <dc:title>{html.escape(title)}</dc:title>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter"/>
  </spine>
</package>"""
            zf.writestr("OEBPS/content.opf", content_opf)

        os.replace(tmp, out_path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def epub_to(src: str | Path, target: str) -> list[Path]:
    """Convert EPUB to PDF, DOCX, TXT, MD, or HTML."""
    src = Path(src)
    target = target.upper()

    # PyMuPDF natively opens EPUB!
    with fitz.open(src) as doc:
        if target == "PDF":
            out = sibling(src, ext=".pdf")
            pdf_bytes = doc.convert_to_pdf()
            out.write_bytes(pdf_bytes)
            return [out]

        full_text = []
        html_blocks = []
        for page in doc:
            full_text.append(page.get_text("text"))
            html_blocks.append(page.get_text("html"))

    text_content = "\n\n".join(full_text)

    if target == "TXT":
        out = sibling(src, ext=".txt")
        out.write_text(text_content, encoding="utf-8")
        return [out]
    elif target in ("MD", "MARKDOWN"):
        out = sibling(src, ext=".md")
        out.write_text(f"# {src.stem}\n\n" + text_content, encoding="utf-8")
        return [out]
    elif target == "HTML":
        out = sibling(src, ext=".html")
        body = "".join(html_blocks)
        out.write_text(f"<html><body><h1>{src.stem}</h1>{body}</body></html>", encoding="utf-8")
        return [out]
    elif target in ("DOCX", "PAGES"):
        out = sibling(src, ext=".docx")
        d = Document()
        d.add_heading(src.stem, level=1)
        for line in text_content.splitlines():
            if line.strip():
                d.add_paragraph(line)
        d.save(out)
        return [out]
    else:
        raise UserError(f"Unsupported EPUB target format: {target}")


def pdf_to_md(src: str | Path) -> list[Path]:
    """Extract structured Markdown from PDF."""
    src = Path(src)
    out = sibling(src, ext=".md")
    parts = [f"# {src.stem}\n"]
    with fitz.open(src) as doc:
        for i, page in enumerate(doc):
            t = page.get_text("text").strip()
            if t:
                parts.append(f"## Page {i + 1}\n\n{t}\n")
    out.write_text("\n".join(parts), encoding="utf-8")
    return [out]


def pdf_to_epub(src: str | Path) -> list[Path]:
    """Convert PDF to EPUB e-book."""
    src = Path(src)
    out = sibling(src, ext=".epub")
    body_parts = []
    with fitz.open(src) as doc:
        for page in doc:
            txt = page.get_text("text")
            paragraphs = "".join(f"<p>{html.escape(p)}</p>" for p in txt.split("\n\n") if p.strip())
            body_parts.append(paragraphs)
    create_epub(src.stem, "".join(body_parts), out)
    return [out]


def pdf_to_xlsx(src: str | Path) -> list[Path]:
    """Extract table rows from PDF into Excel XLSX."""
    src = Path(src)
    out = sibling(src, ext=".xlsx")
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Extracted Tables"

    with fitz.open(src) as doc:
        has_any = False
        for page in doc:
            tabs = page.find_tables()
            for t in tabs:
                for row in t.extract():
                    ws.append([str(c) if c is not None else "" for c in row])
                    has_any = True
        if not has_any:
            # Fallback: extract line by line
            for page in doc:
                for line in page.get_text("text").splitlines():
                    if line.strip():
                        ws.append(line.split())

    wb.save(out)
    return [out]


def doc_to_all(src: str | Path, target: str) -> list[Path]:
    """Convert documents (DOCX, TXT, MD, HTML) to any target."""
    src = Path(src)
    target = target.upper()

    if target == "EPUB":
        out = sibling(src, ext=".epub")
        raw = src.read_text(encoding="utf-8", errors="replace") if src.suffix.lower() != ".docx" else ""
        if not raw:
            from .convert import docx_to_html
            raw = docx_to_html(src)
        else:
            raw = f"<pre>{html.escape(raw)}</pre>"
        create_epub(src.stem, raw, out)
        return [out]

    elif target in ("MD", "MARKDOWN"):
        out = sibling(src, ext=".md")
        if src.suffix.lower() == ".docx":
            from .convert import docx_to_txt
            lines = docx_to_txt(src)[0].read_text(encoding="utf-8").splitlines()
            out.write_text(f"# {src.stem}\n\n" + "\n\n".join(lines), encoding="utf-8")
        else:
            text = src.read_text(encoding="utf-8", errors="replace")
            out.write_text(text, encoding="utf-8")
        return [out]

    elif target == "HTML":
        out = sibling(src, ext=".html")
        if src.suffix.lower() == ".docx":
            from .convert import docx_to_html
            body = docx_to_html(src)
        else:
            text = src.read_text(encoding="utf-8", errors="replace")
            body = f"<pre>{html.escape(text)}</pre>"
        out.write_text(f"<!DOCTYPE html><html><body>{body}</body></html>", encoding="utf-8")
        return [out]

    elif target in ("JPG", "PNG"):
        from .convert import docx_to_pdf, text_to_pdf, pdf_to_images
        pdf = docx_to_pdf(src)[0] if src.suffix.lower() == ".docx" else text_to_pdf(src)[0]
        imgs = pdf_to_images(pdf, target)
        if pdf.exists():
            try:
                pdf.unlink()
            except OSError:
                pass
        return imgs

    raise UserError(f"Unsupported target format for document: {target}")
