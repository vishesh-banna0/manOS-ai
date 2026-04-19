"""
File: setup.py

Purpose:
Quick setup script to install dependencies and verify everything works.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description=""):
    """Run a shell command and return success status."""
    if description:
        print(f"\n▶️  {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ Success")
            return True
        else:
            print(f"   ❌ Failed")
            if result.stderr:
                print(f"   Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False


def check_python():
    """Check Python version."""
    print("\n" + "="*60)
    print("🔍 Checking Python")
    print("="*60)

    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print("✅ Python version OK")
        return True
    else:
        print("❌ Python 3.8+ required")
        return False


def install_dependencies():
    """Install Python dependencies."""
    print("\n" + "="*60)
    print("📦 Installing Dependencies")
    print("="*60)

    return run_command(
        "pip install -r requirements.txt",
        "Installing Python packages"
    )


def check_ollama():
    """Check if Ollama is available."""
    print("\n" + "="*60)
    print("🤖 Checking Ollama")
    print("="*60)

    # Try to import ollama
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✅ Ollama is running")
            models = response.json().get("models", [])
            print(f"   Available models: {len(models)}")
            for model in models[:3]:
                print(f"   • {model.get('name')}")
            return True
        else:
            print("❌ Ollama not responding")
            return False
    except Exception as e:
        print("❌ Ollama not running")
        print("   You need to start Ollama: ollama serve")
        print("   In another terminal, pull a model: ollama pull llama3:8b")
        return False


def create_directories():
    """Create necessary directories."""
    print("\n" + "="*60)
    print("📁 Creating Directories")
    print("="*60)

    dirs = ["outputs", "sample_files"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        print(f"✅ {d}/")


def create_sample_file():
    """Create a sample text file for testing."""
    print("\n" + "="*60)
    print("📝 Creating Sample File")
    print("="*60)

    sample_content = """
Artificial Intelligence and Machine Learning

Artificial Intelligence (AI) refers to the simulation of human intelligence by machines. 
It encompasses machine learning, natural language processing, computer vision, and other 
related fields. AI systems are designed to perform tasks that typically require human 
intelligence, such as learning, reasoning, and problem-solving.

Machine Learning is a subset of AI that focuses on enabling machines to learn from data 
without being explicitly programmed. Instead of following pre-programmed rules, machine 
learning algorithms identify patterns and relationships within large datasets and use these 
patterns to make predictions or decisions.

Deep Learning is a specialized branch of machine learning that uses neural networks with 
multiple layers (hence "deep") to process information. Deep learning has revolutionized fields 
like computer vision, natural language processing, and autonomous systems.

Key Applications:
- Virtual Assistants and Chatbots
- Recommendation Systems
- Image and Speech Recognition
- Autonomous Vehicles
- Medical Diagnosis
- Fraud Detection

The Future of AI:
As AI technology continues to evolve, we can expect more sophisticated applications across 
various industries. However, important considerations include ethical implications, data 
privacy, and ensuring that AI systems are transparent and fair.
    """

    sample_path = Path("sample_files/sample_document.txt")
    sample_path.parent.mkdir(exist_ok=True)

    with open(sample_path, "w", encoding="utf-8") as f:
        f.write(sample_content.strip())

    print(f"✅ Created: {sample_path}")
    print("   You can test with: python main.py sample_files/sample_document.txt")


def verify_installation():
    """Try importing all required modules."""
    print("\n" + "="*60)
    print("✔️  Verifying Imports")
    print("="*60)

    modules = [
        ("requests", "HTTP Client"),
        ("pptx", "PDF Extraction (PyMuPDF + fitz)"),
        ("docx", "DOCX Support"),
    ]

    all_good = True
    for module, desc in modules:
        try:
            __import__(module)
            print(f"✅ {desc} ({module})")
        except ImportError:
            print(f"❌ {desc} ({module}) - Not installed")
            all_good = False

    return all_good


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "="*60)
    print("🚀 Next Steps")
    print("="*60)

    print("""
1. Make sure Ollama is running:
   $ ollama serve

2. In another terminal, pull the default model:
   $ ollama pull llama3:8b

3. Test the playground with the sample file:
   $ python main.py sample_files/sample_document.txt

4. Or with your own file:
   $ python main.py path/to/your/document.pdf

For more examples:
   $ python examples.py

For testing individual components:
   $ python test_pipeline.py path/to/file.pdf

For batch processing:
   $ python batch_process.py ./documents *.pdf

Happy testing! 🎮
    """)


def main():
    """Run all setup steps."""
    print("\n" + "="*60)
    print("🎮 MANOS AI PLAYGROUND - SETUP")
    print("="*60)

    steps = [
        ("Python Version", check_python),
        ("Dependencies", install_dependencies),
        ("Directories", create_directories),
        ("Sample File", create_sample_file),
        ("Imports", verify_installation),
        ("Ollama", check_ollama),
    ]

    results = {}
    for name, func in steps:
        try:
            results[name] = func()
        except Exception as e:
            print(f"❌ Error during {name}: {e}")
            results[name] = False

    # Print summary
    print("\n" + "="*60)
    print("📊 Setup Summary")
    print("="*60)

    for name, success in results.items():
        status = "✅" if success else "⚠️"
        print(f"{status} {name}")

    # Print next steps
    print_next_steps()

    # Check if all critical steps passed
    critical = ["Python Version", "Dependencies", "Imports"]
    if all(results.get(step, False) for step in critical):
        print("\n✅ Setup complete! You're ready to start.")
        if not results.get("Ollama", False):
            print("⚠️  Note: Start Ollama before running main.py")
        return 0
    else:
        print("\n❌ Some setup steps failed. Please fix them and run again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
