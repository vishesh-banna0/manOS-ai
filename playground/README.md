# Manos AI - Playground

A **zero-frills** playground for testing Q&A generation from documents.

No APIs. No database. No frontend. Just pure text processing and question generation.

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Ensure Ollama is Running

Make sure Ollama is running on your system with the default model:

```bash
ollama serve
```

In another terminal, pull the model (first time only):

```bash
ollama pull llama3:8b
```

### 3. Generate Q&A from a File

Simply pass a file path and everything works end-to-end:

```bash
python main.py sample.pdf
python main.py document.txt
python main.py research.docx
```

That's it! Results are automatically saved to `outputs/` folder.

---

## 📁 What's Inside

```
playground/
├── main.py                      # Main entry point
├── config.py                    # Configuration (model, chunk size, etc.)
├── requirements.txt             # Dependencies
├── ai/
│   ├── ingestion/               # File extraction
│   │   ├── pdf_extractor.py     # PDF → Text
│   │   └── text_extractor.py    # TXT/DOCX → Text
│   ├── processing/              # Text processing
│   │   ├── text_chunker.py      # Text → Chunks
│   │   └── text_cleaner.py      # Clean text
│   └── qa_generation/           # Q&A generation
│       └── question_generator.py # Chunks → Q&A pairs
└── outputs/                     # Generated JSON files
```

---

## 🎯 Supported File Types

- **PDF** (.pdf)
- **Text** (.txt)
- **Word** (.docx)

---

## 📊 Pipeline

```
File → Extract Text → Clean Text → Chunk Text → Generate Q&A → Save JSON
```

Each step shows progress indicators so you know what's happening.

---

## 🔧 Customization

Edit `config.py` to adjust:

- **Model**: Change from `llama3:8b` to `mistral`, `neural-chat`, etc.
- **Chunk Size**: Default 500 words (smaller = more, shorter chunks)
- **Chunk Overlap**: Default 100 words (context overlap between chunks)
- **Output Directory**: Where JSON results are saved

---

## 📝 Output Format

Results are saved as JSON with this structure:

```json
{
  "metadata": {
    "file_path": "sample.pdf",
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
      "difficulty": "medium",
      "topic": "...",
      "chunk_id": 1,
      "chunk_title": "..."
    }
  ]
}
```

---

## 🐛 Troubleshooting

### "Cannot connect to Ollama"
- Make sure Ollama is running: `ollama serve`
- Check OLLAMA_URL in config.py (default: http://localhost:11434)

### "Model not found"
- Pull the model: `ollama pull llama3:8b`
- Or change model in config.py

### "File not found"
- Use absolute paths: `python main.py C:\path\to\file.pdf`
- Or relative paths from playground directory

### Empty Q&A results
- Check if the extracted text has enough content
- Try a longer document
- Check Ollama output for errors

---

## 💡 Use Cases

- ✅ Test Q&A generation locally without API overhead
- ✅ Experiment with different models and chunk sizes
- ✅ Debug and understand the full pipeline
- ✅ Generate training data for flashcards
- ✅ Quick prototyping and iteration

---

## 🎮 Interactive Testing

You can also use this as a Python library in your own scripts:

```python
from main import generate_qa_from_file, display_results

# Generate
results = generate_qa_from_file("document.pdf")

# Display
display_results(results)

# Access data
qa_pairs = results["qa_pairs"]
for qa in qa_pairs:
    print(f"Q: {qa['question']}")
    print(f"A: {qa['answer']}")
```

---

## 📦 Requirements

- Python 3.8+
- Ollama (running locally)
- PyMuPDF (PDF extraction)
- python-docx (DOCX extraction)
- requests (HTTP calls to Ollama)

---

Enjoy! 🚀
