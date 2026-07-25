"""
File: pdf_extractor.py

Purpose:
Extract text from PDF using PyMuPDF (fitz).

Error handling note:
This used to catch every exception and return "", so a corrupt file, an
encrypted file and a scanned image-only file all surfaced as the same
"No text could be extracted" message - none of which tells the user what to
do about it. Each failure mode now raises with its own actionable message.
"""

from __future__ import annotations

import fitz  # PyMuPDF


class DocumentExtractionError(ValueError):
    """Extraction failed. The message is user-facing."""


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from a PDF.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted raw text, with "--- PAGE n ---" separators that the chunker
        consumes as page metadata.

    Raises:
        DocumentExtractionError: unreadable, encrypted, or no text layer.
    """
    try:
        document = fitz.open(file_path)
    except Exception as exc:
        raise DocumentExtractionError(
            f"This file could not be opened as a PDF. It may be corrupt or "
            f"incomplete ({exc})."
        ) from exc

    try:
        if document.needs_pass:
            raise DocumentExtractionError(
                "This PDF is password-protected. Remove the password and upload it again."
            )

        if document.page_count == 0:
            raise DocumentExtractionError("This PDF has no pages.")

        parts = []
        characters = 0

        for page_number, page in enumerate(document, start=1):
            try:
                page_text = page.get_text()
            except Exception as exc:  # one bad page should not kill the document
                print(f"[pdf] page {page_number} failed to extract: {exc}")
                continue

            characters += len(page_text.strip())
            parts.append(f"\n\n--- PAGE {page_number} ---\n\n")
            parts.append(page_text)

        if characters == 0:
            raise DocumentExtractionError(
                f"No text layer found in this PDF ({document.page_count} pages). "
                f"It is most likely a scan or images of text, which needs OCR "
                f"before it can be indexed."
            )

        return "".join(parts)
    finally:
        document.close()
