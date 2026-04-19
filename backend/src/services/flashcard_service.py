"""
File: flashcard_service.py

Purpose:
Business logic for flashcards and spaced repetition.
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..ai.ingestion.pdf_extractor import extract_text_from_pdf
from ..ai.processing.text_chunker import chunk_text
from ..ai.processing.text_cleaner import clean_text
from ..models.document import Document
from ..repositories.flashcard_repository import FlashcardRepository
from ..models.flashcard import Flashcard
from ..models.qa_pair import QAPair
from ..services.qa_service import QAService


class FlashcardService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = FlashcardRepository(db)
        self.qa_service = QAService(db)

    def _read_document_text(self, file_path: str) -> str:
        if file_path.lower().endswith(".pdf"):
            return extract_text_from_pdf(file_path)

        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def _bootstrap_qa_pairs(self, instance_id: int):
        documents = self.db.query(Document).filter(Document.instance_id == instance_id).all()
        unique_paths = []
        seen_paths = set()

        for document in documents:
            if document.file_path in seen_paths:
                continue
            seen_paths.add(document.file_path)
            unique_paths.append(document.file_path)

        created_pairs = []
        for file_path in unique_paths:
            raw_text = self._read_document_text(file_path)
            if not raw_text.strip():
                continue

            cleaned_text = clean_text(raw_text)
            for chunk in chunk_text(cleaned_text):
                created_pairs.extend(self.qa_service.generate_and_store(instance_id, chunk["text"]))

        return created_pairs

    # --------------------------------------------------

    def generate_from_qa(self, instance_id: int):
        """
        Convert all QAPairs into flashcards.
        """

        qa_pairs = self.db.query(QAPair).filter(
            QAPair.instance_id == instance_id
        ).all()

        if not qa_pairs:
            qa_pairs = self._bootstrap_qa_pairs(instance_id)

        if not qa_pairs:
            raise ValueError(
                "No Q&A pairs found for this instance. Upload a document first and make sure question generation is available."
            )

        existing_questions = {
            flashcard.question
            for flashcard in self.db.query(Flashcard).filter(Flashcard.instance_id == instance_id).all()
        }

        flashcards = []

        for qa in qa_pairs:
            if qa.question in existing_questions:
                continue
            flashcards.append(
                Flashcard(
                    instance_id=instance_id,
                    question=qa.question,
                    answer=qa.answer
                )
            )
            existing_questions.add(qa.question)

        if flashcards:
            self.repo.bulk_create(flashcards)

        return len(flashcards)

    # --------------------------------------------------

    def get_due_flashcards(self, instance_id: int):
        return self.repo.get_due_flashcards(instance_id)

    # --------------------------------------------------

    def review_flashcard(self, flashcard_id: int, correct: bool):
        """
        Apply spaced repetition logic.
        """

        flashcard = self.db.query(Flashcard).filter(
            Flashcard.id == flashcard_id
        ).first()

        if not flashcard:
            return None

        if correct:
            flashcard.repetitions += 1
            flashcard.interval = int(flashcard.interval * flashcard.ease_factor)
            flashcard.ease_factor += 0.1
        else:
            flashcard.repetitions = 0
            flashcard.interval = 1
            flashcard.ease_factor = 2.5

        flashcard.last_reviewed = datetime.utcnow()
        flashcard.next_review = datetime.utcnow() + timedelta(days=flashcard.interval)

        return self.repo.update(flashcard)
