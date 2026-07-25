"""
File: file_handler.py

Purpose:
Validate and persist uploaded files into per-instance storage.

Validation happens here rather than downstream because a bad file should be
rejected with a clear reason before it becomes a Document row, a saved blob and
a confusing "no text could be extracted" message three layers later.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from fastapi import UploadFile

from ..core.config import settings

BASE_DATA_PATH = settings.DATA_DIR / "instances"

MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown", ".rst"}

_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]")


class UploadRejected(ValueError):
    """The uploaded file cannot be accepted. Message is user-facing."""


def safe_filename(name: str) -> str:
    """
    Reduce an arbitrary client-supplied filename to a safe basename.

    `file.filename` is attacker-controlled: without this, a name like
    "../../../backend/src/main.py" would escape the instance directory and
    overwrite source files.
    """
    name = (name or "").strip()
    # Take the basename only - drop any directory components, both separators.
    name = name.replace("\\", "/").split("/")[-1]
    # Strip accents so the result stays filesystem-portable.
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = _UNSAFE.sub("_", name).strip(". ")

    if not name:
        name = "upload"

    # Leave room for the instance directory prefix on Windows' path limit.
    if len(name) > 120:
        stem, dot, suffix = name.rpartition(".")
        name = (stem[:110] + dot + suffix) if dot else name[:120]

    return name


def save_file(instance_id: int, file: UploadFile) -> str:
    """
    Validate and save an uploaded file to its instance folder.

    Raises:
        UploadRejected: empty file, unsupported type, or over the size limit.

    Returns:
        Absolute path to the saved file.
    """
    filename = safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise UploadRejected(
            f"Unsupported file type '{suffix or 'unknown'}'. "
            f"Supported: {', '.join(sorted(ALLOWED_SUFFIXES))}."
        )

    instance_path = BASE_DATA_PATH / str(instance_id)
    instance_path.mkdir(parents=True, exist_ok=True)
    file_path = instance_path / filename

    # Stream to disk so a large upload is not held in memory, and so the size
    # limit is enforced as we go rather than after buffering everything.
    written = 0
    try:
        file.file.seek(0)
    except (AttributeError, OSError):
        pass

    try:
        with open(file_path, "wb") as handle:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise UploadRejected(
                        f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                    )
                handle.write(chunk)
    except UploadRejected:
        file_path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        file_path.unlink(missing_ok=True)
        raise UploadRejected(f"Could not save the file: {exc}") from exc

    if written == 0:
        # The common real-world cause is an interrupted download or a cloud
        # placeholder that never hydrated - the file on the user's machine is
        # genuinely empty, and nothing downstream can recover from that.
        file_path.unlink(missing_ok=True)
        raise UploadRejected(
            f"'{filename}' is empty (0 bytes). The source file has no content - "
            f"check that it downloaded fully, then upload it again."
        )

    return str(file_path)
