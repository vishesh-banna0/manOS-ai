"""
File: question_generator.py

Purpose:
Generate structured Q&A pairs from text chunks using Ollama when available,
with a local fallback so the app still works offline.
"""

import json
import re

import requests

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama3:8b"


def _normalize_topic(text: str) -> str:
    words = [word for word in re.findall(r"[A-Za-z0-9]+", text) if word]
    if not words:
        return "this topic"
    return " ".join(words[:6])


def _fallback_questions(chunk_text: str):
    topic = _normalize_topic(chunk_text)
    raw_sentences = re.split(r"(?<=[.!?])\s+", chunk_text)

    sentences = []
    seen = set()
    for sentence in raw_sentences:
        cleaned = " ".join(sentence.split()).strip()
        if len(cleaned) < 40:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        sentences.append(cleaned)

    if not sentences:
        snippet = " ".join(chunk_text.split())[:240].strip()
        if not snippet:
            return []
        sentences = [snippet]

    prompts = [
        ("easy", f"What is one key idea from {topic}?"),
        ("medium", f"How would you summarize this point about {topic}?"),
        ("hard", f"Why is this statement important in the context of {topic}?"),
    ]

    fallback = []
    for index, (difficulty, question) in enumerate(prompts):
        answer = sentences[min(index, len(sentences) - 1)]
        fallback.append(
            {
                "question": question,
                "answer": answer,
                "difficulty": difficulty,
                "topic": topic,
            }
        )

    return fallback


def generate_questions(chunk_text: str):
    """
    Generate Q&A pairs from chunk.

    Returns:
        List[dict]
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
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=60,
        )
    except requests.RequestException as e:
        print(f"Ollama request failed: {e}")
        return _fallback_questions(chunk_text)

    if response.status_code != 200:
        print("ERROR:", response.text)
        return _fallback_questions(chunk_text)

    output = response.json()["response"]

    try:
        start = output.find("[")
        end = output.rfind("]") + 1
        json_str = output[start:end]
        parsed = json.loads(json_str)
        return parsed or _fallback_questions(chunk_text)
    except Exception as e:
        print("JSON parsing failed:", e)
        print("RAW OUTPUT:", output)
        return _fallback_questions(chunk_text)
