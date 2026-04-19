"""
File: question_generator.py

Purpose:
Generate structured Q&A pairs from text chunks using LLM (Ollama).
"""

import requests
import json


OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3:8b"


def generate_questions(chunk_text: str, model: str = MODEL):
    """
    Generate Q&A pairs from chunk.

    Args:
        chunk_text (str): Text chunk to generate questions from
        model (str): Ollama model to use

    Returns:
        List[dict]: List of Q&A pairs
    """

    prompt = f"""
You are an expert teacher.

From the following content, generate 3 high-quality questions.

Rules:
- Include a mix of easy, medium, and hard questions
- Provide clear and correct answers
- Assign difficulty: easy / medium / hard
- Identify the topic

Return ONLY JSON in this format:

[
  {{
    "question": "...",
    "answer": "...",
    "difficulty": "...",
    "topic": "..."
  }}
]

CONTENT:
\"\"\"
{chunk_text}
\"\"\"
"""

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        if response.status_code != 200:
            print(f"❌ Ollama Error: {response.text}")
            return []

        output = response.json()["response"]

        # Try parsing JSON
        try:
            # Extract JSON part (important safety)
            start = output.find("[")
            end = output.rfind("]") + 1
            json_str = output[start:end]

            return json.loads(json_str)

        except Exception as e:
            print(f"⚠️ JSON parsing failed: {e}")
            print(f"Raw output: {output}")
            return []

    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Ollama at {OLLAMA_URL}")
        print("   Make sure Ollama is running: ollama serve")
        return []
    except Exception as e:
        print(f"❌ Error generating questions: {e}")
        return []


def batch_generate_qa(chunks: list, model: str = MODEL) -> list:
    """
    Generate Q&A pairs for multiple chunks.

    Args:
        chunks (list): List of chunk dictionaries
        model (str): Ollama model to use

    Returns:
        list: All generated Q&A pairs with chunk metadata
    """
    all_qa_pairs = []

    for i, chunk in enumerate(chunks, 1):
        print(f"\n📝 Processing chunk {i}/{len(chunks)}...")
        
        qa_pairs = generate_questions(chunk["text"], model)
        
        for qa in qa_pairs:
            qa["chunk_id"] = chunk["chunk_id"]
            qa["chunk_title"] = chunk.get("title", "")
            all_qa_pairs.append(qa)
        
        print(f"   ✅ Generated {len(qa_pairs)} Q&A pairs")

    return all_qa_pairs
