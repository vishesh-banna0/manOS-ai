"""
Tests for upload validation and extraction error reporting.

Motivated by a real report: a 0-byte PDF (an interrupted download) was accepted,
saved, given a Document row, and then surfaced as "No text could be extracted
from this file" - which tells the user nothing about what went wrong.
"""

import io

import fitz
import pytest
from fastapi import UploadFile

from backend.src.ai.ingestion.pdf_extractor import (
    DocumentExtractionError,
    extract_text_from_pdf,
)
from backend.src.utils import file_handler
from backend.src.utils.file_handler import UploadRejected, safe_filename, save_file


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(data))


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(file_handler, "BASE_DATA_PATH", tmp_path / "instances")
    return tmp_path / "instances"


# ------------------------------------------------------------ safe_filename


def test_safe_filename_strips_directory_traversal():
    assert safe_filename("../../../backend/src/main.py") == "main.py"
    assert safe_filename(r"..\..\windows\system32\evil.pdf") == "evil.pdf"


def test_safe_filename_handles_hostile_and_empty_names():
    assert "/" not in safe_filename("a/b/c.pdf")
    assert safe_filename("") == "upload"
    assert safe_filename("...") == "upload"
    # Accents normalised, unsafe punctuation replaced.
    assert safe_filename("résumé;rm -rf.pdf").endswith(".pdf")


def test_safe_filename_truncates_long_names():
    assert len(safe_filename("x" * 400 + ".pdf")) <= 120


# ------------------------------------------------------------------- saving


def test_empty_file_is_rejected_and_not_written(storage):
    with pytest.raises(UploadRejected, match="empty"):
        save_file(1, _upload("ML_book.pdf", b""))

    # Nothing should be left behind for a rejected upload.
    assert not (storage / "1" / "ML_book.pdf").exists()


def test_oversized_file_is_rejected(storage, monkeypatch):
    monkeypatch.setattr(file_handler, "MAX_UPLOAD_BYTES", 1024)

    with pytest.raises(UploadRejected, match="larger than"):
        save_file(1, _upload("big.pdf", b"x" * 5000))

    assert not (storage / "1" / "big.pdf").exists()


def test_unsupported_extension_is_rejected(storage):
    with pytest.raises(UploadRejected, match="Unsupported file type"):
        save_file(1, _upload("malware.exe", b"MZ..."))


def test_valid_file_is_saved(storage):
    path = save_file(1, _upload("notes.txt", b"hello world"))
    assert (storage / "1" / "notes.txt").read_bytes() == b"hello world"
    assert path.endswith("notes.txt")


def test_traversal_filename_stays_inside_instance_dir(storage):
    path = save_file(7, _upload("../../escaped.txt", b"data"))
    assert (storage / "7" / "escaped.txt").exists()
    assert str(storage / "7") in path


# --------------------------------------------------------------- extraction


def test_corrupt_pdf_raises_actionable_error(tmp_path):
    bad = tmp_path / "corrupt.pdf"
    bad.write_bytes(b"this is definitely not a pdf")

    with pytest.raises(DocumentExtractionError, match="could not be opened"):
        extract_text_from_pdf(str(bad))


def test_pdf_without_text_layer_mentions_ocr(tmp_path):
    """A scan is a valid PDF with pages but no extractable text."""
    document = fitz.open()
    document.new_page()  # blank page, no text
    scan = tmp_path / "scan.pdf"
    document.save(str(scan))
    document.close()

    with pytest.raises(DocumentExtractionError, match="OCR"):
        extract_text_from_pdf(str(scan))


def test_valid_pdf_extracts_text_with_page_markers(tmp_path):
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Backpropagation computes gradients.")
    good = tmp_path / "good.pdf"
    document.save(str(good))
    document.close()

    text = extract_text_from_pdf(str(good))
    assert "Backpropagation" in text
    assert "--- PAGE 1 ---" in text
