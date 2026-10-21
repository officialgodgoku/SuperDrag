"""Archive utilities: Zip/Unzip for folders and files with multiple popular compression logics
(Store, Standard Deflate, Max Deflate, Bzip2, LZMA, Tar.gz, Tar)."""
from __future__ import annotations

import os
import shutil
import tarfile
import zipfile
from pathlib import Path

from .util import UserError, sibling

ARCHIVE_EXTS = {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z"}

# Archive targets available when zipping folders or files
ARCHIVE_TARGETS = [
    "ZIP",
    "ZIP (Max)",
    "ZIP (Store)",
    "ZIP (BZIP2)",
    "ZIP (LZMA)",
    "TAR.GZ",
    "TAR",
]

ARCHIVE_TOOLS = ["Extract Here", "Extract to Folder"]


def is_archive(path: str | Path) -> bool:
    p = Path(path)
    name = p.name.lower()
    return any(name.endswith(ext) for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz")) or p.suffix.lower() in ARCHIVE_EXTS


def create_archive(srcs: list[str | Path], target: str) -> list[Path]:
    """Compress files or folder(s) using the specified compression logic."""
    src_paths = [Path(s) for s in srcs]
    first = src_paths[0]

    # Output filename
    if len(src_paths) == 1:
        base_name = first.name if first.is_dir() else first.stem
    else:
        base_name = f"{first.parent.name} Archive"

    out_dir = first.parent

    # Determine extension and format
    if "TAR.GZ" in target:
        ext = ".tar.gz"
    elif "TAR" in target:
        ext = ".tar"
    else:
        ext = ".zip"

    out = sibling(first, ext=ext)
    tmp = out.with_name(f".~{out.stem}.part{ext}")

    try:
        if ext == ".zip":
            # Select compression algorithm
            if "Store" in target:
                comp = zipfile.ZIP_STORED
                level = None
            elif "BZIP2" in target:
                comp = zipfile.ZIP_BZIP2
                level = None
            elif "LZMA" in target:
                comp = zipfile.ZIP_LZMA
                level = None
            elif "Max" in target:
                comp = zipfile.ZIP_DEFLATED
                level = 9
            else:  # Standard Deflate
                comp = zipfile.ZIP_DEFLATED
                level = 6

            kwargs = {"compression": comp}
            if level is not None and comp == zipfile.ZIP_DEFLATED:
                kwargs["compresslevel"] = level

            with zipfile.ZipFile(tmp, "w", **kwargs) as zf:
                for sp in src_paths:
                    if sp.is_dir():
                        for root, _, files in os.walk(sp):
                            for f in files:
                                full = Path(root) / f
                                arcname = full.relative_to(sp.parent)
                                zf.write(full, arcname=str(arcname))
                    else:
                        zf.write(sp, arcname=sp.name)

        elif "TAR.GZ" in target:
            with tarfile.open(tmp, "w:gz") as tf:
                for sp in src_paths:
                    arcname = sp.name
                    tf.add(sp, arcname=arcname)

        elif "TAR" in target:
            with tarfile.open(tmp, "w") as tf:
                for sp in src_paths:
                    arcname = sp.name
                    tf.add(sp, arcname=arcname)

        os.replace(tmp, out)
        return [out]

    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def extract_archive(src: str | Path, to_subfolder: bool = False) -> list[Path]:
    """Safely extract archive contents either directly into parent folder or to a subfolder."""
    src = Path(src)
    if to_subfolder:
        folder_name = src.name
        for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip", ".tar", ".gz", ".7z"):
            if folder_name.lower().endswith(ext):
                folder_name = folder_name[:-len(ext)]
                break
        dest = src.parent / folder_name
        dest.mkdir(parents=True, exist_ok=True)
    else:
        dest = src.parent

    name_lower = src.name.lower()

    if name_lower.endswith(".zip"):
        with zipfile.ZipFile(src, "r") as zf:
            # Safe extraction avoiding directory traversal
            for member in zf.infolist():
                norm = os.path.normpath(member.filename)
                if norm.startswith("..") or os.path.isabs(norm):
                    continue
                zf.extract(member, dest)
        return [dest]

    elif any(name_lower.endswith(ext) for ext in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        with tarfile.open(src, "r:*") as tf:
            for member in tf.getmembers():
                norm = os.path.normpath(member.name)
                if norm.startswith("..") or os.path.isabs(norm):
                    continue
                tf.extract(member, dest)
        return [dest]

    elif name_lower.endswith(".gz"):
        import gzip
        out_name = src.stem
        out_file = dest / out_name
        with gzip.open(src, "rb") as f_in, open(out_file, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        return [out_file]

    raise UserError(f"Unsupported archive format: {src.suffix}")
