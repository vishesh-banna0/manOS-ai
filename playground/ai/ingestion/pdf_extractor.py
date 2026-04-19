"""
File: pdf_extractor.py

Purpose:
Extract text from PDF using PyMuPDF (fitz).
Optimized for large PDFs and structured extraction.
"""

import fitz  # PyMuPDF


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF file.

    Args:
        file_path (str): Path to PDF file

    Returns:
        str: Extracted raw text
    """

    text = ""

    try:
        doc = fitz.open(file_path)

        for page_num, page in enumerate(doc):
            page_text = page.get_text()

            # Add page separator (important for chunking later)
            text += f"\n\n--- PAGE {page_num + 1} ---\n\n"
            text += page_text

        doc.close()

    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return ""

    return text
