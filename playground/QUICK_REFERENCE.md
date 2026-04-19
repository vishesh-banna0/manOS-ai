# Manos AI Playground - Quick Reference

## 🚀 Quick Commands

### Basic Usage
```bash
# Generate Q&A from any file
python main.py document.pdf
python main.py article.txt
python main.py presentation.docx
```

### Testing
```bash
# Test individual pipeline steps
python test_pipeline.py file.pdf

# Run all 7 examples
python examples.py 1
python examples.py 2
# ... up to 7
```

### Batch Processing
```bash
# Process all PDFs in a folder
python batch_process.py ./documents *.pdf

# Process all text files
python batch_process.py ./data *.txt
```

### Setup
```bash
# One-time setup
python setup.py
```

---

## 🤖 Ollama Commands

```bash
# Start Ollama
ollama serve

# List installed models
ollama list

# Pull a model
ollama pull llama3:8b
ollama pull mistral
ollama pull neural-chat

# Remove a model
ollama rm llama3:8b
```

---

## 📝 File Options

| Extension | Status |
|-----------|--------|
| .pdf      | ✅ Supported |
| .txt      | ✅ Supported |
| .docx     | ✅ Supported |
| .md       | Use as .txt |
| .doc      | Convert to .docx |

---

## 🔧 Configuration

### Edit `config.py`:

```python
# OLLAMA settings
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3:8b"  # or: mistral, neural-chat

# Processing settings
CHUNK_SIZE = 500      # Words per chunk
CHUNK_OVERLAP = 100   # Overlap between chunks

# Output settings
OUTPUT_DIR = "outputs"
SAVE_JSON = True
```

### Python Usage

```python
from main import generate_qa_from_file

# Basic
results = generate_qa_from_file("file.pdf")

# Custom
results = generate_qa_from_file(
    "file.pdf",
    chunk_size=300,
    overlap=50,
    model="mistral"
)
```

---

## 📂 Directory Structure

```
Results saved to: outputs/
Sample files in: sample_files/

outputs/
├── qa_results_20240416_103045.json
├── qa_results_20240416_110530.json
└── ...
```

---

## 🔍 Finding Results

```bash
# List all results
ls outputs/

# View size of results
ls -la outputs/

# Open latest result (Windows)
explorer outputs/
```

---

## 💾 Working with Results

### Load and inspect
```python
import json

with open("outputs/qa_results_*.json") as f:
    data = json.load(f)

# Access parts
qa_pairs = data["qa_pairs"]
metadata = data["metadata"]
chunks = data["chunks"]
```

### Filter by difficulty
```python
easy = [qa for qa in qa_pairs if qa["difficulty"] == "easy"]
hard = [qa for qa in qa_pairs if qa["difficulty"] == "hard"]
```

### Export to CSV
```python
import csv

with open("export.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["question", "answer", "difficulty"])
    w.writeheader()
    w.writerows(qa_pairs)
```

---

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| "Cannot connect to Ollama" | Run `ollama serve` first |
| "Model not found" | Run `ollama pull llama3:8b` |
| "No Q&A generated" | File might be scanned PDF or empty |
| "Process is slow" | Use smaller model: `mistral` |
| "Out of memory" | Reduce CHUNK_SIZE in config |

---

## 📊 Output Structure

```json
{
  "metadata": {
    "file_path": "...",
    "chunk_count": 10,
    "qa_count": 30,
    "model": "llama3:8b",
    "generated_at": "2024-04-16T..."
  },
  "qa_pairs": [
    {
      "question": "...",
      "answer": "...",
      "difficulty": "easy|medium|hard",
      "topic": "...",
      "chunk_id": 1
    }
  ]
}
```

---

## 🎯 Use Case Examples

### Generate flashcard data
```bash
python main.py textbook.pdf
# → JSON → Import to flashcard app
```

### Test different models
```bash
python main.py file.pdf  # uses llama3:8b (default)
# Edit config.py, change to mistral
python main.py file.pdf  # compare results
```

### Process documentation
```bash
python batch_process.py ./docs *.pdf
# → Generate training dataset
```

### Debug extraction
```bash
python test_pipeline.py problem_file.pdf
# See at which step it fails
```

---

## 🌟 Pro Tips

1. **Faster testing:** Use `mistral` model (smaller, faster)
2. **Better quality:** Use `llama2` or `neural-chat`
3. **More Q&A:** Reduce CHUNK_SIZE to 300
4. **Better context:** Increase CHUNK_OVERLAP to 150
5. **First run cache:** Models download on first use, then cached
6. **Batch processing:** Process multiple files at once with `batch_process.py`
7. **Export formats:** Results are JSON → easy to convert to CSV, MD, etc.

---

## 🔗 Useful Links

- [Ollama Models](https://ollama.ai/library)
- [Manos AI Repo](../README.md)
- [Full Documentation](README.md)
- [Getting Started Guide](GETTING_STARTED.md)

---

Last updated: 2024-04-16
