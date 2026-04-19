"""
File: batch_process.py

Purpose:
Process multiple files in batch and generate Q&A for all of them.
Useful for bulk testing and generating training data.
"""

import os
import glob
from pathlib import Path
from main import generate_qa_from_file, save_results, display_results


def process_directory(directory: str, file_pattern: str = "*.*", chunk_size: int = 500):
    """
    Process all matching files in a directory.

    Args:
        directory (str): Directory containing files
        file_pattern (str): File pattern to match (*.pdf, *.txt, etc.)
        chunk_size (int): Chunk size for processing

    Returns:
        list: Results for each file
    """

    directory = Path(directory)
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        return []

    # Find files
    pattern = str(directory / file_pattern)
    files = glob.glob(pattern)

    if not files:
        print(f"❌ No files found matching: {pattern}")
        return []

    print(f"\n📦 Found {len(files)} files to process")

    all_results = []

    for i, file_path in enumerate(files, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(files)}] Processing: {Path(file_path).name}")
        print(f"{'='*60}")

        try:
            results = generate_qa_from_file(file_path, chunk_size=chunk_size)
            all_results.append(results)

            # Save individual results
            if "error" not in results:
                output_file = f"outputs/batch_{Path(file_path).stem}.json"
                save_results(results, output_file)

        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            all_results.append({"error": str(e), "file": file_path})

    return all_results


def generate_summary(results: list):
    """
    Generate summary of batch processing.

    Args:
        results (list): Results from all files
    """

    print(f"\n{'='*60}")
    print("📊 BATCH PROCESSING SUMMARY")
    print(f"{'='*60}")

    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]

    print(f"Total files: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed files:")
        for r in failed:
            print(f"  - {r.get('file', 'Unknown')}: {r.get('error')}")

    if successful:
        total_qa = sum(r["metadata"]["qa_count"] for r in successful)
        total_chunks = sum(r["metadata"]["chunk_count"] for r in successful)
        print(f"\nTotal Q&A pairs generated: {total_qa}")
        print(f"Total chunks: {total_chunks}")

        print("\nPer-file breakdown:")
        for r in successful:
            meta = r["metadata"]
            print(f"  - {meta['file_path']}")
            print(f"    Chunks: {meta['chunk_count']}")
            print(f"    Q&A: {meta['qa_count']}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        directory = sys.argv[1]
        pattern = sys.argv[2] if len(sys.argv) > 2 else "*.*"
    else:
        print("Usage: python batch_process.py <directory> [file_pattern]")
        print("\nExamples:")
        print("  python batch_process.py ./documents *.pdf")
        print("  python batch_process.py ./files *.txt")
        sys.exit(0)

    # Process directory
    results = process_directory(directory, pattern)

    # Generate summary
    generate_summary(results)

    print(f"\n✅ Batch processing complete!")
    print(f"   Results saved to: outputs/")
