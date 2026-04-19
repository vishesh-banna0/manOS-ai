import requests

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"


def get_embedding(text: str):
    """
    Generate embedding safely.
    """

    #  VERY IMPORTANT: limit input size
    text = text[:2000]

    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={
            "model": EMBED_MODEL,
            "prompt": text
        }
    )

    if response.status_code != 200:
        print("ERROR RESPONSE:", response.text)
        raise Exception("Embedding failed")

    return response.json()["embedding"]