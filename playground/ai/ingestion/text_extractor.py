"""
File: text_extractor.py

Purpose:
Extract text from various file formats (.txt, .docx, etc).
"""

from pathlib import Path


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text from plain text file.

    Args:
        file_path (str): Path to text file

    Returns:
        str: File contents
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text from DOCX file.

    Args:
        file_path (str): Path to DOCX file

    Returns:
        str: Extracted text
    """
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        print(f"Error extracting DOCX: {e}")
        return ""


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from file based on extension.

    Args:
        file_path (str): Path to file

    Returns:
        str: Extracted text
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return ""
    
    extension = file_path.suffix.lower()
    
    if extension == '.pdf':
        from .pdf_extractor import extract_text_from_pdf
        return extract_text_from_pdf(str(file_path))
    elif extension == '.txt':
        return extract_text_from_txt(str(file_path))
    elif extension == '.docx':
        return extract_text_from_docx(str(file_path))
    else:
        print(f"❌ Unsupported file type: {extension}")
        return ""
