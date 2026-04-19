"""
File: test_pipeline.py

Purpose:
Test individual stages of the pipeline in isolation.
Useful for debugging and testing each component.
"""

from ai.ingestion.text_extractor import extract_text_from_file
from ai.processing.text_chunker import chunk_text
from ai.processing.text_cleaner import clean_text
from ai.qa_generation.question_generator import generate_questions


def test_extraction(file_path: str):
    """Test text extraction only."""
    print(f"\n🧪 Testing extraction: {file_path}")
    text = extract_text_from_file(file_path)
    print(f"   Extracted: {len(text)} characters")
    print(f"   Preview: {text[:200]}...")
    return text


def test_cleaning(text: str):
    """Test text cleaning only."""
    print(f"\n🧪 Testing cleaning")
    cleaned = clean_text(text)
    print(f"   Original: {len(text)} characters")
    print(f"   Cleaned: {len(cleaned)} characters")
    print(f"   Preview: {cleaned[:200]}...")
    return cleaned


def test_chunking(text: str, chunk_size: int = 500, overlap: int = 100):
    """Test text chunking only."""
    print(f"\n🧪 Testing chunking (size={chunk_size}, overlap={overlap})")
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    print(f"   Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks[:3], 1):
        print(f"   Chunk {i}: {chunk['word_count']} words - {chunk['title'][:50]}...")
    return chunks


def test_qa_generation(text: str, model: str = "llama3:8b"):
    """Test Q&A generation only."""
    print(f"\n🧪 Testing Q&A generation (model={model})")
    qa_pairs = generate_questions(text, model=model)
    print(f"   Generated {len(qa_pairs)} Q&A pairs")
    for i, qa in enumerate(qa_pairs, 1):
        print(f"\n   Q{i}: {qa.get('question')}")
        print(f"   A{i}: {qa.get('answer')}")
        print(f"   Difficulty: {qa.get('difficulty')}")


def run_all_tests(file_path: str):
    """Run all tests in sequence."""
    print("\n" + "="*60)
    print("🧪 RUNNING PIPELINE TESTS")
    print("="*60)

    # Test extraction
    text = test_extraction(file_path)

    # Test cleaning
    cleaned_text = test_cleaning(text)

    # Test chunking
    chunks = test_chunking(cleaned_text)

    # Test QA generation on first chunk
    if chunks:
        print("\n🧪 Testing Q&A generation on first chunk...")
        test_qa_generation(chunks[0]["text"])

    print("\n" + "="*60)
    print("✅ All tests completed!")
    print("="*60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        run_all_tests(file_path)
    else:
        print("Usage: python test_pipeline.py <file_path>")
        print("Example: python test_pipeline.py sample.pdf")
