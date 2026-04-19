"""
File: main.py

Purpose:
Main playground script - entry point for testing and generating Q&A pairs.
Simply provide a file path and everything works end-to-end.
"""

import json
import os
from pathlib import Path
from datetime import datetime

from ai.ingestion.text_extractor import extract_text_from_file
from ai.processing.text_chunker import chunk_text
from ai.processing.text_cleaner import clean_text
from ai.qa_generation.question_generator import batch_generate_qa


def generate_qa_from_file(file_path: str, chunk_size: int = 500, overlap: int = 100, model: str = "llama3:8b") -> dict:
    """
    End-to-end pipeline: File → Text → Chunks → Q&A

    Args:
        file_path (str): Path to file (PDF, TXT, DOCX)
        chunk_size (int): Words per chunk
        overlap (int): Overlap between chunks
        model (str): Ollama model to use

    Returns:
        dict: Results with metadata
    """

    print("\n" + "="*60)
    print("🎮 PLAYGROUND - Q&A GENERATOR")
    print("="*60)

    # Step 1: Extract text
    print(f"\n Step 1: Extracting text from {file_path}...")
    raw_text = extract_text_from_file(file_path)

    if not raw_text:
        return {"error": "Failed to extract text"}

    print(f" Extracted {len(raw_text)} characters")

    # Step 2: Clean text
    print(f"\n Step 2: Cleaning text...")
    cleaned_text = clean_text(raw_text)
    print(f"    Cleaned to {len(cleaned_text)} characters")

    # Step 3: Chunk text
    print(f"\n  Step 3: Chunking text (chunk_size={chunk_size}, overlap={overlap})...")
    chunks = chunk_text(cleaned_text, chunk_size=chunk_size, overlap=overlap)
    print(f"    Created {len(chunks)} chunks")

    # Step 4: Generate Q&A
    print(f"\n🤖 Step 4: Generating Q&A pairs using {model}...")
    qa_pairs = batch_generate_qa(chunks, model=model)
    print(f"    Generated {len(qa_pairs)} total Q&A pairs")

    # Prepare results
    results = {
        "metadata": {
            "file_path": str(file_path),
            "file_size_chars": len(raw_text),
            "cleaned_size_chars": len(cleaned_text),
            "chunk_count": len(chunks),
            "qa_count": len(qa_pairs),
            "model": model,
            "generated_at": datetime.now().isoformat()
        },
        "chunks": chunks,
        "qa_pairs": qa_pairs
    }

    return results


def save_results(results: dict, output_file: str = None) -> str:
    """
    Save results to JSON file.

    Args:
        results (dict): Results dictionary
        output_file (str): Output file path (auto-generated if not provided)

    Returns:
        str: Path to saved file
    """

    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/qa_results_{timestamp}.json"

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Results saved to: {output_file}")
    return output_file


def display_results(results: dict):
    """
    Display results in a readable format.

    Args:
        results (dict): Results dictionary
    """

    if "error" in results:
        print(f" Error: {results['error']}")
        return

    meta = results.get("metadata", {})
    qa_pairs = results.get("qa_pairs", [])

    print("\n" + "="*60)
    print(" RESULTS SUMMARY")
    print("="*60)
    print(f"File: {meta.get('file_path')}")
    print(f"Total Chunks: {meta.get('chunk_count')}")
    print(f"Total Q&A Pairs: {meta.get('qa_count')}")
    print(f"Model: {meta.get('model')}")
    print(f"Generated: {meta.get('generated_at')}")

    print("\n" + "-"*60)
    print("📝 SAMPLE Q&A PAIRS (First 5)")
    print("-"*60)

    for i, qa in enumerate(qa_pairs[:5], 1):
        print(f"\n{i}. [{qa.get('difficulty', 'N/A').upper()}] {qa.get('question')}")
        print(f"   Answer: {qa.get('answer')}")
        print(f"   Topic: {qa.get('topic')}")
        if qa.get('chunk_id'):
            print(f"   From Chunk: {qa.get('chunk_id')}")

    if len(qa_pairs) > 5:
        print(f"\n... and {len(qa_pairs) - 5} more Q&A pairs")

    print("\n" + "="*60)


if __name__ == "__main__":
    import sys

    # Example usage
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        # Default example
        print("\nUsage: python main.py <file_path>\n")
        print("Example: python main.py sample.pdf")
        print("         python main.py document.txt")
        print("\nFiles supported: .pdf, .txt, .docx")
        sys.exit(0)

    # Generate Q&A
    results = generate_qa_from_file(file_path)

    # Display results
    display_results(results)

    # Save results
    if "error" not in results:
        save_results(results)
