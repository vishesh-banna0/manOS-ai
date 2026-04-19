# Getting Started with Manos AI Playground

Welcome! This guide will help you get up and running in minutes.

---

## 🎯 30-Second Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Ollama (in one terminal)
ollama serve

# 3. Pull the model (in another terminal)
ollama pull llama3:8b

# 4. Run the playground
python main.py sample_files/sample_document.txt
```

Done! Check the `outputs/` folder for results.

---

## 📋 Complete Setup

### Step 1: Prerequisites

You need:
- Python 3.8+ ([Download](https://www.python.org/downloads/))
- Ollama ([Download](https://ollama.ai))

### Step 2: Install Python Packages

```bash
pip install -r requirements.txt
```

### Step 3: Start Ollama

```bash
ollama serve
```

In another terminal, pull the default model:

```bash
ollama pull llama3:8b
```

You can also pull other models:
```bash
ollama pull mistral      # Faster model
ollama pull neural-chat  # Good balance
ollama pull llama2       # Alternative
```

### Step 4: Verify Installation

```bash
python setup.py
```

This will check everything and create sample files.

---

## 🎮 Basic Usage

### Generate Q&A from a Single File

```bash
python main.py document.pdf
python main.py textfile.txt
python main.py slides.docx
```

Results appear in the console **and** are saved to `outputs/` as JSON.

### With Custom Settings

```bash
# Smaller chunks = more Q&A pairs
python main.py file.pdf chunk_size=300 overlap=50

# Different model
python main.py file.pdf model=mistral
```

*Note: Pass settings by editing `config.py` instead of command line for now.*

### Batch Process Multiple Files

```bash
python batch_process.py ./my_documents *.pdf
```

Generates Q&A for all PDFs in a directory.

---

## 📂 Project Structure

```
playground/
├── main.py                 ← Main command-line interface
├── setup.py               ← One-time setup script
├── test_pipeline.py       ← Test individual components
├── batch_process.py       ← Process multiple files
├── examples.py            ← Usage examples
├── config.py              ← Configuration settings
├── README.md              ← Full documentation
│
├── ai/                    ← Core AI modules
│   ├── ingestion/         ← Extract text from files
│   ├── processing/        ← Clean and chunk text
│   └── qa_generation/     ← Generate Q&A pairs
│
├── outputs/               ← Generated JSON results
├── sample_files/          ← Sample files for testing
│
├── requirements.txt       ← Python dependencies
└── .gitignore
```

---

## 🔄 Pipeline Steps

```
📄 File              
  ↓
📖 Extract Text     main.py uses: extract_text_from_file()
  ↓
🧹 Clean Text       Clean URLs, extra spaces, etc.
  ↓
✂️  Chunk Text      Split into 500-word chunks
  ↓
🤖 Generate Q&A     Use Ollama model to create questions
  ↓
💾 Save JSON        Results stored in outputs/
```

---

## 🛠️ Testing & Debugging

### Test Individual Steps

```bash
python test_pipeline.py document.pdf
```

Shows:
- How much text was extracted
- How text cleaning affects length
- How many chunks were created
- Sample Q&A from first chunk

### Test a Specific Component

```python
# In a Python script or notebook:
from ai.ingestion.text_extractor import extract_text_from_file

text = extract_text_from_file("file.pdf")
print(len(text))  # See how many characters
```

### View Full Pipeline

```python
from main import generate_qa_from_file

results = generate_qa_from_file("file.pdf")
print(results.keys())  # See structure
```

---

## 📊 Output Format

Results are saved as JSON with this structure:

```json
{
  "metadata": {
    "file_path": "document.pdf",
    "chunk_count": 10,
    "qa_count": 30,
    "model": "llama3:8b",
    "generated_at": "2024-04-16T10:30:00"
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
      "topic": "Physics",
      "chunk_id": 1
    }
  ]
}
```

---

## 🎓 Common Use Cases

### Generate Training Data

```bash
python main.py textbook.pdf
# Gets Q&A pairs for creating flashcards
```

### Quick Testing

```python
from main import generate_qa_from_file

for model in ["llama3:8b", "mistral"]:
    results = generate_qa_from_file("doc.txt", model=model)
    print(f"{model}: {results['metadata']['qa_count']} Q&A pairs")
```

### Custom Export

```python
from main import generate_qa_from_file
import json

results = generate_qa_from_file("file.pdf")

# Save only hard questions
hard_qa = [qa for qa in results["qa_pairs"] if qa["difficulty"] == "hard"]

with open("hard_questions.json", "w") as f:
    json.dump(hard_qa, f, indent=2)
```

---

## ⚙️ Customization

Edit `config.py` to change:

```python
# Model to use
OLLAMA_MODEL = "llama3:8b"  # Try: mistral, neural-chat, llama2

# How to split text
CHUNK_SIZE = 500    # Smaller = more Q&A
CHUNK_OVERLAP = 100 # Context between chunks

# Where results go
OUTPUT_DIR = "outputs"
```

---

## 🐛 Troubleshooting

### "Cannot connect to Ollama"

**Solution:**
```bash
# Terminal 1 - Start Ollama
ollama serve

# Terminal 2 - Verify it's running
curl http://localhost:11434/api/tags
```

### "Model not found"

**Solution:**
```bash
ollama pull llama3:8b
# or use a different model:
ollama pull mistral
```

### "File not found"

Use full paths:
```bash
# Bad
python main.py file.pdf

# Good
python main.py C:\Users\YourName\Documents\file.pdf
# or relative to playground folder
python main.py ../path/to/file.pdf
```

### "Out of memory" errors

Try a smaller model or reduce chunk size:
```python
# In config.py
CHUNK_SIZE = 300  # Smaller chunks
```

### No Q&A generated

- Make sure the file has real text (not scanned PDF)
- Try a longer document
- Check that Ollama is actually running
- Look at Ollama console for error messages

---

## 🚀 Next Steps

1. **Run the setup:**
   ```bash
   python setup.py
   ```

2. **Test with sample file:**
   ```bash
   python main.py sample_files/sample_document.txt
   ```

3. **Try your own file:**
   ```bash
   python main.py your_document.pdf
   ```

4. **Check results:**
   ```bash
   # Look in outputs/ folder
   ls outputs/
   ```

5. **Explore examples:**
   ```bash
   python examples.py 1
   python examples.py 2
   # ... etc
   ```

---

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Main entry point - CLI interface |
| `setup.py` | One-time setup and verification |
| `test_pipeline.py` | Test individual pipeline steps |
| `batch_process.py` | Process multiple files |
| `examples.py` | 7 usage examples |
| `config.py` | Configuration settings |
| `ai/ingestion/` | Text extraction (PDF, TXT, DOCX) |
| `ai/processing/` | Text cleaning and chunking |
| `ai/qa_generation/` | Q&A generation using Ollama |

---

## 💡 Tips

- **First time slow?** Ollama models are large. First run downloads and caches them.
- **Want faster?** Try `mistral` model (smaller, faster)
- **Want better?** Try `llama2` or `neural-chat`
- **Customize everything** - edit files directly, no configuration files needed
- **JSON outputs** - easy to parse and load into other tools
- **No database** - everything is local and portable

---

## 🎯 That's It!

You now have a fully working playground for:
✅ Extract text from any document
✅ Split into smart chunks
✅ Generate Q&A pairs using AI
✅ Test locally without APIs
✅ Export results for further processing

Start exploring!

```bash
python main.py sample_files/sample_document.txt
```

Questions? Check the [README.md](README.md) or look at [examples.py](examples.py).
