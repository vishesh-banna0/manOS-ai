import sys
import os
from hashlib import md5

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# IMPORTS
from backend.src.ai.ingestion.pdf_extractor import extract_text_from_pdf
from backend.src.ai.processing.text_cleaner import clean_text
from backend.src.ai.processing.text_chunker import chunk_text
from backend.src.ai.embeddings.embedding_generator import get_embedding
from backend.src.services.qa_service import QAService
from backend.src.core.database import SessionLocal


# -----------------------------
# Utility: Hash for duplicates
# -----------------------------
def hash_text(text):
    return md5(text.encode()).hexdigest()


def main():
    print(" STEP 1: Extracting PDF...")

    file_path = "data/instances/1/chapter_Neural_Networks.pdf"

    if not os.path.exists(file_path):
        print(" File not found:", file_path)
        return

    raw_text = extract_text_from_pdf(file_path)

    print(" Extraction done")
    print(raw_text[:300])

    # ----------------------------------------------------

    print("\n STEP 2: Cleaning text...")
    cleaned_text = clean_text(raw_text)

    print(" Cleaning done")
    print(cleaned_text[:300])

    # ----------------------------------------------------

    print("\n STEP 3: Chunking...")

    chunks = chunk_text(cleaned_text, chunk_size=500, overlap=100)

    if not chunks:
        print(" No chunks generated")
        return

    print(f" Total chunks: {len(chunks)}")
    print(" Sample chunk:")
    print(chunks[0]["text"][:200])

    # ----------------------------------------------------

    print("\n STEP 4: Embedding (Testing first 3)...")

    for i, chunk in enumerate(chunks[:3]):
        print(f"\nEmbedding chunk {i+1}...")
        emb = get_embedding(chunk["text"][:2000])
        print(f" Embedding size: {len(emb)}")

    # ----------------------------------------------------

    print("\n STEP 5: Q&A Generation + Storage...")

    db = SessionLocal()

    total_saved = 0
    seen_hashes = set()

    try:
        qa_service = QAService(db)

        instance_id = 1
        print(f" Using instance_id = {instance_id}")

        for i, chunk in enumerate(chunks):
            print(f"\n Processing chunk {i+1}/{len(chunks)}")

            # 🔥 IMPORTANT: renamed variable (fixes your error)
            chunk_content = chunk["text"].strip()

            # Skip weak chunks
            if len(chunk_content) < 200:
                print(" Skipped (too small)")
                continue

            # Limit size for LLM
            chunk_content = chunk_content[:1500]

            try:
                saved_qas = qa_service.generate_and_store(
                    instance_id=instance_id,
                    chunk_text=chunk_content
                )

                if not saved_qas:
                    print(" No Q&A generated")
                    continue

                for qa in saved_qas:
                    qa_hash = hash_text(qa.question)

                    if qa_hash in seen_hashes:
                        print(" Duplicate skipped")
                        continue

                    seen_hashes.add(qa_hash)
                    total_saved += 1

                    print("\n--- SAVED Q&A ---")
                    print("Q:", qa.question)
                    print("A:", qa.answer)
                    print("Difficulty:", qa.difficulty)
                    print("Topic:", qa.topic)

            except Exception as e:
                print(f" Error in chunk {i+1}: {str(e)}")

        print(f"\n TOTAL UNIQUE Q&A GENERATED: {total_saved}")

    except Exception as e:
        print(" ERROR during Q&A generation:", str(e))

    finally:
        db.close()

    # ----------------------------------------------------

    print("\n FULL PIPELINE COMPLETED")


if __name__ == "__main__":
    main()