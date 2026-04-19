"""
File: document_service.py

Purpose:
Handles business logic for document ingestion.
"""

from sqlalchemy.orm import Session
from fastapi import UploadFile
from ..repositories.document_repository import DocumentRepository
from ..utils.file_handler import save_file
from ..ai.ingestion.pdf_extractor import extract_text_from_pdf
from ..ai.processing.text_chunker import chunk_text
from ..ai.processing.text_cleaner import clean_text
from ..services.qa_service import QAService
from ..services.flashcard_service import FlashcardService


class DocumentService:
    def __init__(self, db: Session):
        self.repo = DocumentRepository(db)
        self.qa_service = QAService(db)
        self.flashcard_service = FlashcardService(db)

    def upload_document(self, instance_id: int, file: UploadFile):
        """
        Save file, extract text, generate Q&A pairs, and create flashcards.
        """

        # Save file locally
        file_path = save_file(instance_id, file)

        # Save in DB
        document = self.repo.create(
            instance_id=instance_id,
            file_name=file.filename,
            file_path=file_path
        )

        # Extract text from the uploaded file
        if file.filename.lower().endswith('.pdf'):
            raw_text = extract_text_from_pdf(file_path)
        else:
            # For other file types, read as text
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()

        if not raw_text.strip():
            return {"message": "No text could be extracted from the file", "document": document}

        # Clean the text
        cleaned_text = clean_text(raw_text)

        # Chunk the text
        chunks = chunk_text(cleaned_text)

        # Generate Q&A pairs and flashcards for each chunk
        total_qa_pairs = 0
        total_flashcards = 0

        for chunk in chunks:
            # Generate Q&A pairs from chunk
            qa_pairs = self.qa_service.generate_and_store(instance_id, chunk["text"])
            total_qa_pairs += len(qa_pairs)

        # Generate flashcards from all Q&A pairs
        if total_qa_pairs > 0:
            flashcards_created = self.flashcard_service.generate_from_qa(instance_id)
            total_flashcards = flashcards_created

        generation_warning = None
        if total_qa_pairs == 0:
            generation_warning = (
                "Document uploaded, but no Q&A pairs were generated. "
                "Check that Ollama is running and the configured model is available."
            )

        response = {
            "message": f"Document processed successfully. Generated {total_qa_pairs} Q&A pairs and {total_flashcards} flashcards.",
            "document": document,
            "stats": {
                "qa_pairs": total_qa_pairs,
                "flashcards": total_flashcards,
                "chunks": len(chunks)
            }
        }

        if generation_warning:
            response["warning"] = generation_warning

        return response
