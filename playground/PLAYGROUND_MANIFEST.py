"""
PLAYGROUND MANIFEST

This file maps out the entire playground project structure and purpose.
"""

# ==============================================================
# 📂 DIRECTORY STRUCTURE
# ==============================================================

STRUCTURE = """
playground/
│
├─ 📄 DOCUMENTATION
│  ├─ README.md                  # Full documentation and features
│  ├─ GETTING_STARTED.md         # Step-by-step setup guide
│  ├─ QUICK_REFERENCE.md         # Cheat sheet for commands
│  └─ PLAYGROUND_MANIFEST.py     # This file
│
├─ 🚀 MAIN SCRIPTS
│  ├─ main.py                    # Primary entry point - Generate Q&A
│  ├─ setup.py                   # One-time setup and verification
│  ├─ test_pipeline.py           # Test individual pipeline steps
│  ├─ batch_process.py           # Batch process multiple files
│  └─ examples.py                # 7 usage examples
│
├─ ⚙️  CONFIGURATION
│  ├─ config.py                  # User-editable settings
│  ├─ requirements.txt           # Python dependencies
│  └─ .gitignore                 # Git ignore patterns
│
├─ 🤖 CORE AI MODULES (ai/)
│  ├─ __init__.py
│  │
│  ├─ ingestion/                 # Extract text from files
│  │  ├─ __init__.py
│  │  ├─ pdf_extractor.py        # PDF → Text (PyMuPDF)
│  │  └─ text_extractor.py       # TXT/DOCX → Text (unified)
│  │
│  ├─ processing/                # Clean and chunk text
│  │  ├─ __init__.py
│  │  ├─ text_chunker.py         # Split text into chunks
│  │  └─ text_cleaner.py         # Normalize and clean text
│  │
│  └─ qa_generation/             # Generate Q&A pairs
│     ├─ __init__.py
│     └─ question_generator.py   # LLM-based Q&A generation
│
├─ 📁 OUTPUTS (Auto-created)
│  └─ outputs/                   # JSON results from generation
│
└─ 📁 SAMPLES (Auto-created)
   └─ sample_files/              # Sample documents for testing
      └─ sample_document.txt     # Auto-generated test file
"""

print(STRUCTURE)


# ==============================================================
# 📋 FILE DESCRIPTIONS
# ==============================================================

FILE_DESCRIPTIONS = {
    # Documentation
    "README.md": {
        "purpose": "Complete documentation with features, troubleshooting, and API reference",
        "user_editable": False,
        "critical": True,
    },
    "GETTING_STARTED.md": {
        "purpose": "Step-by-step setup guide for first-time users",
        "user_editable": False,
        "critical": True,
    },
    "QUICK_REFERENCE.md": {
        "purpose": "Cheat sheet with common commands and quick solutions",
        "user_editable": False,
        "critical": False,
    },

    # Main Scripts
    "main.py": {
        "purpose": "Main entry point - Run with file path to generate Q&A",
        "usage": "python main.py document.pdf",
        "user_editable": True,
        "critical": True,
    },
    "setup.py": {
        "purpose": "One-time setup: install deps, verify config, create samples",
        "usage": "python setup.py",
        "user_editable": False,
        "critical": True,
    },
    "test_pipeline.py": {
        "purpose": "Test individual pipeline components for debugging",
        "usage": "python test_pipeline.py document.pdf",
        "user_editable": True,
        "critical": False,
    },
    "batch_process.py": {
        "purpose": "Process multiple files in a directory at once",
        "usage": "python batch_process.py ./docs *.pdf",
        "user_editable": True,
        "critical": False,
    },
    "examples.py": {
        "purpose": "7 usage examples demonstrating different scenarios",
        "usage": "python examples.py 1",
        "user_editable": True,
        "critical": False,
    },

    # Configuration
    "config.py": {
        "purpose": "Adjustable settings (model, chunk size, etc)",
        "user_editable": True,
        "critical": True,
        "settings": [
            "OLLAMA_URL",
            "OLLAMA_MODEL",
            "CHUNK_SIZE",
            "CHUNK_OVERLAP",
            "OUTPUT_DIR",
        ]
    },
    "requirements.txt": {
        "purpose": "Python package dependencies",
        "user_editable": False,
        "critical": True,
    },

    # Core modules
    "ai/ingestion/pdf_extractor.py": {
        "purpose": "Extract text from PDF files using PyMuPDF",
        "exported_function": "extract_text_from_pdf(file_path: str) -> str",
    },
    "ai/ingestion/text_extractor.py": {
        "purpose": "Universal text extractor for PDF, TXT, DOCX",
        "exported_function": "extract_text_from_file(file_path: str) -> str",
    },
    "ai/processing/text_chunker.py": {
        "purpose": "Split text into overlapping chunks",
        "exported_function": "chunk_text(text: str, chunk_size: int, overlap: int) -> List[Dict]",
    },
    "ai/processing/text_cleaner.py": {
        "purpose": "Normalize and clean text (remove URLs, extra spaces, etc)",
        "exported_function": "clean_text(text: str) -> str",
    },
    "ai/qa_generation/question_generator.py": {
        "purpose": "Generate Q&A pairs using Ollama LLM",
        "exported_functions": [
            "generate_questions(chunk_text: str, model: str) -> List[Dict]",
            "batch_generate_qa(chunks: list, model: str) -> List[Dict]",
        ]
    },
}


# ==============================================================
# 🔄 PIPELINE FLOW
# ==============================================================

PIPELINE = """
User provides file path
        ↓
main.py - main() function
        ↓
Step 1: extract_text_from_file()
        ↓ (raw text)
Step 2: clean_text()
        ↓ (cleaned text)
Step 3: chunk_text()
        ↓ (list of chunks with metadata)
Step 4: batch_generate_qa()
        ↓ (Q&A pairs with difficulty/topic)
Results saved to JSON in outputs/
"""

print("\n" + PIPELINE)


# ==============================================================
# 🎯 QUICK START
# ==============================================================

QUICK_START = """
1. python setup.py
   - Install dependencies
   - Verify Ollama connection
   - Create sample files

2. ollama serve
   - Start Ollama (keep running)

3. ollama pull llama3:8b
   - Download the default model

4. python main.py sample_files/sample_document.txt
   - Test with sample file

5. python main.py your_document.pdf
   - Use with your own file

6. Check outputs/ for JSON results
"""

print("\n" + QUICK_START)


# ==============================================================
# 🔧 CUSTOMIZATION POINTS
# ==============================================================

CUSTOMIZATION = {
    "configuration": [
        "Edit config.py to change model, chunk size, overlap, output directory",
        "No need to restart - changes take effect immediately",
    ],
    "processing": [
        "Modify ai/processing/text_cleaner.py to change text cleaning logic",
        "Edit ai/processing/text_chunker.py to change chunking strategy",
    ],
    "generation": [
        "Edit ai/qa_generation/question_generator.py to change prompt or model",
        "Customize Q&A format or difficulty detection",
    ],
    "extraction": [
        "Add new file format support in ai/ingestion/text_extractor.py",
        "Improve PDF extraction with custom parameters in pdf_extractor.py",
    ],
}

print("\n❇️  CUSTOMIZATION POINTS:")
for category, items in CUSTOMIZATION.items():
    print(f"\n{category.upper()}:")
    for item in items:
        print(f"  - {item}")


# ==============================================================
# 🚀 USAGE PATTERNS
# ==============================================================

PATTERNS = """
PATTERN 1: Simple end-to-end (Most Common)
    python main.py file.pdf
    → JSON saved to outputs/
    
PATTERN 2: Test individual step
    python test_pipeline.py file.pdf
    → See each step's output
    
PATTERN 3: Batch processing
    python batch_process.py ./docs *.pdf
    → Process many files
    
PATTERN 4: Use as Python library
    from main import generate_qa_from_file
    results = generate_qa_from_file("file.pdf")
    
PATTERN 5: Custom processing
    from ai.ingestion.text_extractor import extract_text_from_file
    from ai.processing.text_chunker import chunk_text
    # ... build custom pipeline
"""

print(PATTERNS)


# ==============================================================
# 📊 OUTPUT FORMAT
# ==============================================================

OUTPUT = """
Results saved as JSON with structure:

{
  "metadata": {
    "file_path": "document.pdf",
    "file_size_chars": 50000,
    "cleaned_size_chars": 45000,
    "chunk_count": 10,
    "qa_count": 30,
    "model": "llama3:8b",
    "generated_at": "2024-04-16T10:30:45.123456"
  },
  "chunks": [
    {
      "chunk_id": 1,
      "text": "...",
      "title": "...",
      "word_count": 500
    }
  ],
  "qa_pairs": [
    {
      "question": "What is...?",
      "answer": "...",
      "difficulty": "easy|medium|hard",
      "topic": "...",
      "chunk_id": 1,
      "chunk_title": "..."
    }
  ]
}
"""

print(OUTPUT)


# ==============================================================
# 🔗 IMPORTS & DEPENDENCIES
# ==============================================================

IMPORTS = {
    "External Libraries": [
        "requests - HTTP calls to Ollama",
        "pymupdf (fitz) - PDF extraction",
        "python-docx - DOCX support",
        "python-dotenv - Environment variables",
    ],
    "Standard Library": [
        "json - JSON serialization",
        "pathlib - File path handling",
        "datetime - Timestamps",
        "re - Text regex cleaning",
    ],
    "Internal Modules": [
        "ai.ingestion.text_extractor",
        "ai.processing.text_chunker",
        "ai.processing.text_cleaner",
        "ai.qa_generation.question_generator",
    ]
}

print("\n📚 IMPORTS & DEPENDENCIES:")
for category, items in IMPORTS.items():
    print(f"\n{category}:")
    for item in items:
        print(f"  - {item}")


# ==============================================================
# ✅ VERIFICATION CHECKLIST
# ==============================================================

CHECKLIST = """
After setup, verify:

□ Python 3.8+ installed
□ requirements.txt installed
□ Ollama running (ollama serve)
□ Model downloaded (ollama pull llama3:8b)
□ setup.py runs successfully
□ Sample file created in sample_files/
□ Imports all work (no missing packages)
□ First run: python main.py sample_files/sample_document.txt
□ Check outputs/ for generated JSON
□ Review metadata to confirm Q&A count > 0
"""

print("\n" + CHECKLIST)


# ==============================================================
# 🆘 COMMON ISSUES & FIXES
# ==============================================================

TROUBLESHOOTING = {
    "Cannot connect to Ollama": [
        "Solution: Run 'ollama serve' in another terminal first",
        "Verify: curl http://localhost:11434/api/tags",
    ],
    "Model not found": [
        "Solution: ollama pull llama3:8b",
        "Or change OLLAMA_MODEL in config.py to different model",
    ],
    "Empty Q&A results": [
        "Check: File has real text (not scanned PDF)",
        "Try: Longer document with more content",
        "Check: Ollama is actually responding",
    ],
    "Process too slow": [
        "Try: Faster model in config (mistral instead of llama3)",
        "Or: Reduce CHUNK_SIZE for fewer chunks to process",
    ],
    "File not found": [
        "Use: Full path: C:\\path\\to\\file.pdf",
        "Or: Relative to playground folder",
    ],
}

print("\n🆘 COMMON ISSUES & FIXES:")
for issue, solutions in TROUBLESHOOTING.items():
    print(f"\n{issue}:")
    for solution in solutions:
        print(f"  {solution}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("📚 PLAYGROUND MANIFEST")
    print("="*60)
    print("\nAll information above describes the playground structure.")
    print("\nFor detailed setup: python setup.py")
    print("For quick start: cat GETTING_STARTED.md")
    print("For command ref: cat QUICK_REFERENCE.md")
    print("\nHappy testing! 🎮")
    print("="*60 + "\n")
