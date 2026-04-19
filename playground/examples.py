"""
File: examples.py

Purpose:
Example usage patterns for the playground.
Shows how to use different features and scenarios.
"""

from main import generate_qa_from_file, save_results, display_results
from ai.ingestion.text_extractor import extract_text_from_file
from ai.processing.text_chunker import chunk_text
from ai.processing.text_cleaner import clean_text
import json


# ============================================================
# EXAMPLE 1: Basic usage - file path to Q&A
# ============================================================

def example_basic():
    """Simplest usage: just pass a file path."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Usage")
    print("="*60)

    # Generate Q&A
    results = generate_qa_from_file("sample.pdf")

    # Display in console
    display_results(results)

    # Save to file
    save_results(results)


# ============================================================
# EXAMPLE 2: Custom configuration
# ============================================================

def example_custom_config():
    """Use custom chunk size and model."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Custom Configuration")
    print("="*60)

    results = generate_qa_from_file(
        file_path="sample.pdf",
        chunk_size=300,  # Smaller chunks = more Q&A pairs
        overlap=50,
        model="mistral"  # Different model
    )

    display_results(results)
    save_results(results, "outputs/custom_config.json")


# ============================================================
# EXAMPLE 3: Access and manipulate results
# ============================================================

def example_access_results():
    """Work with results programmatically."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Access Results")
    print("="*60)

    results = generate_qa_from_file("sample.pdf")

    if "error" in results:
        print("❌ Error:", results["error"])
        return

    # Get metadata
    meta = results["metadata"]
    print(f"\n✅ Generated {meta['qa_count']} Q&A pairs")

    # Filter by difficulty
    easy_qa = [qa for qa in results["qa_pairs"] if qa["difficulty"] == "easy"]
    hard_qa = [qa for qa in results["qa_pairs"] if qa["difficulty"] == "hard"]

    print(f"   Easy questions: {len(easy_qa)}")
    print(f"   Hard questions: {len(hard_qa)}")

    # Export easy questions only
    easy_results = {
        "metadata": meta,
        "qa_pairs": easy_qa
    }
    save_results(easy_results, "outputs/easy_questions.json")


# ============================================================
# EXAMPLE 4: Process and filter
# ============================================================

def example_filter():
    """Filter Q&A pairs by topic."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Filter by Topic")
    print("="*60)

    results = generate_qa_from_file("sample.pdf")

    # Group by topic
    by_topic = {}
    for qa in results["qa_pairs"]:
        topic = qa.get("topic", "Unknown")
        if topic not in by_topic:
            by_topic[topic] = []
        by_topic[topic].append(qa)

    print(f"\n📚 Found {len(by_topic)} topics:")
    for topic, pairs in by_topic.items():
        print(f"   {topic}: {len(pairs)} questions")


# ============================================================
# EXAMPLE 5: Step-by-step processing
# ============================================================

def example_step_by_step():
    """Process each step manually for more control."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Step-by-Step Processing")
    print("="*60)

    file_path = "sample.pdf"

    # Step 1: Extract
    print("Step 1: Extracting text...")
    text = extract_text_from_file(file_path)
    print(f"  → {len(text)} characters")

    # Step 2: Clean
    print("Step 2: Cleaning text...")
    cleaned = clean_text(text)
    print(f"  → {len(cleaned)} characters")

    # Step 3: Chunk with custom parameters
    print("Step 3: Chunking text...")
    chunks = chunk_text(cleaned, chunk_size=600, overlap=150)
    print(f"  → {len(chunks)} chunks")

    # Step 4: Process only first 5 chunks
    print("Step 4: Processing first 5 chunks...")
    from ai.qa_generation.question_generator import batch_generate_qa
    qa_pairs = batch_generate_qa(chunks[:5])
    print(f"  → {len(qa_pairs)} Q&A pairs")

    # Save
    results = {
        "metadata": {
            "file_path": file_path,
            "chunks_processed": 5,
            "qa_count": len(qa_pairs)
        },
        "qa_pairs": qa_pairs
    }
    save_results(results, "outputs/first_5_chunks.json")


# ============================================================
# EXAMPLE 6: Compare models
# ============================================================

def example_compare_models():
    """Generate Q&A with different models to compare."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Compare Models")
    print("="*60)

    models = ["llama3:8b", "mistral", "neural-chat"]
    file_path = "sample.pdf"

    # Only process first chunk to save time
    text = extract_text_from_file(file_path)
    cleaned = clean_text(text)
    chunks = chunk_text(cleaned)

    if chunks:
        first_chunk = chunks[0]["text"]

        from ai.qa_generation.question_generator import generate_questions

        for model in models:
            print(f"\n🤖 Testing with {model}...")
            qa = generate_questions(first_chunk, model=model)
            print(f"   Generated {len(qa)} Q&A pairs")

            if qa:
                print(f"   Sample question: {qa[0].get('question', 'N/A')[:60]}...")


# ============================================================
# EXAMPLE 7: Export to different formats
# ============================================================

def example_export_formats():
    """Export results to different formats."""
    print("\n" + "="*60)
    print("EXAMPLE 7: Export Formats")
    print("="*60)

    results = generate_qa_from_file("sample.pdf")
    qa_pairs = results.get("qa_pairs", [])

    # Export as CSV
    import csv

    print("\n📄 Exporting to CSV...")
    with open("outputs/qa_pairs.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "answer", "difficulty", "topic"])
        writer.writeheader()
        writer.writerows(qa_pairs)
    print("   Saved: outputs/qa_pairs.csv")

    # Export as markdown
    print("\n📝 Exporting to Markdown...")
    with open("outputs/qa_pairs.md", "w", encoding="utf-8") as f:
        f.write("# Generated Q&A Pairs\n\n")
        for i, qa in enumerate(qa_pairs, 1):
            f.write(f"## {i}. {qa['question']}\n\n")
            f.write(f"**Answer:** {qa['answer']}\n\n")
            f.write(f"**Difficulty:** {qa['difficulty']} | **Topic:** {qa['topic']}\n\n")
            f.write("---\n\n")
    print("   Saved: outputs/qa_pairs.md")


# ============================================================
# Run Examples
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        example_num = sys.argv[1]
        examples = {
            "1": example_basic,
            "2": example_custom_config,
            "3": example_access_results,
            "4": example_filter,
            "5": example_step_by_step,
            "6": example_compare_models,
            "7": example_export_formats,
        }

        if example_num in examples:
            examples[example_num]()
        else:
            print(f"❌ Unknown example: {example_num}")
            print(f"Available: {', '.join(examples.keys())}")
    else:
        print("\n📚 Available Examples:\n")
        print("1. example_basic - Simple file to Q&A")
        print("2. example_custom_config - Custom chunk size and model")
        print("3. example_access_results - Work with results programmatically")
        print("4. example_filter - Filter Q&A by topic")
        print("5. example_step_by_step - Manual step-by-step processing")
        print("6. example_compare_models - Compare different AI models")
        print("7. example_export_formats - Export to CSV and Markdown")
        print("\nRun: python examples.py <number>")
        print("Example: python examples.py 1")
