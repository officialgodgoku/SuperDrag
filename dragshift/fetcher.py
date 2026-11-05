"""Web and clipboard drag source fetcher.

Brings sources that aren't local files yet (dragged out of web browsers like
Chrome, Edge, Firefox, or from clipboard buffers) onto disk so they can be
converted, compressed, or edited directly on the radial dial.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CACHE_DIR = Path(tempfile.gettempdir()) / "SuperDrag_Cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_path(url_or_data: str, ext: str = ".png") -> Path:
    h = hashlib.sha256(url_or_data.encode("utf-8", "replace")).hexdigest()[:16]
    return CACHE_DIR / f"web_{h}{ext}"


def parse_data_uri(uri: str) -> tuple[bytes, str] | None:
    """Parse a data: URI into raw bytes and a file extension."""
    m = re.match(r"^data:(?:image|text)/([a-zA-Z0-9\+\-]+);base64,(.+)$", uri, re.DOTALL)
    if not m:
        return None
    raw_subtype = m.group(1).lower()
    ext_map = {"jpeg": ".jpg", "svg+xml": ".svg", "plain": ".txt", "markdown": ".md"}
    ext = ext_map.get(raw_subtype, f".{raw_subtype}")
    try:
        data = base64.b64decode(m.group(2))
        return data, ext
    except Exception:
        return None


def fetch_url(url: str, timeout: float = 4.0) -> Path | None:
    """Download a remote URL to the SuperDrag cache."""
    if url.startswith("data:"):
        parsed = parse_data_uri(url)
        if parsed:
            data, ext = parsed
            path = _cache_path(url, ext)
            path.write_bytes(data)
            return path
        return None

    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme not in ("http", "https"):
        return None

    # Derive extension from path
    url_path = parsed_url.path.lower()
    cand_ext = os.path.splitext(url_path)[1]
    if not cand_ext or len(cand_ext) > 6:
        cand_ext = ".png"

    dest = _cache_path(url, cand_ext)
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SuperDrag/2.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "").lower()
            if "jpeg" in content_type:
                cand_ext = ".jpg"
            elif "png" in content_type:
                cand_ext = ".png"
            elif "webp" in content_type:
                cand_ext = ".webp"
            elif "gif" in content_type:
                cand_ext = ".gif"
            elif "svg" in content_type:
                cand_ext = ".svg"
            elif "pdf" in content_type:
                cand_ext = ".pdf"

            data = resp.read(25 * 1024 * 1024)  # cap at 25 MB
            dest = _cache_path(url, cand_ext)
            dest.write_bytes(data)
            return dest
    except Exception:
        return None


def extract_sources_from_mimedata(mime_data: Any) -> list[str]:
    """Inspect QMimeData and resolve local file paths or cached web sources."""
    paths: list[str] = []

    # 1. First check direct local file URLs
    if hasattr(mime_data, "urls"):
        for qurl in mime_data.urls():
            if qurl.isLocalFile():
                lf = qurl.toLocalFile()
                if lf and os.path.exists(lf):
                    paths.append(lf)
            else:
                url_str = qurl.toString()
                fetched = fetch_url(url_str)
                if fetched and fetched.exists():
                    paths.append(str(fetched))

    if paths:
        return paths

    # 2. Check for raw image payload in drag object
    if hasattr(mime_data, "hasImage") and mime_data.hasImage():
        try:
            qimg = mime_data.imageData()
            if qimg is not None and not qimg.isNull():
                dest = CACHE_DIR / f"dropped_image_{os.getpid()}_{id(mime_data)}.png"
                qimg.save(str(dest), "PNG")
                if dest.exists():
                    return [str(dest)]
        except Exception:
            pass

    # 3. Check for HTML img tags
    if hasattr(mime_data, "hasHtml") and mime_data.hasHtml():
        html = mime_data.html() or ""
        imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for img_url in imgs:
            fetched = fetch_url(img_url)
            if fetched and fetched.exists():
                paths.append(str(fetched))
        if paths:
            return paths

    # 4. Check for raw text containing a URL
    if hasattr(mime_data, "hasText") and mime_data.hasText():
        txt = (mime_data.text() or "").strip()
        if txt.startswith(("http://", "https://", "data:image/")):
            fetched = fetch_url(txt)
            if fetched and fetched.exists():
                return [str(fetched)]

    return paths
