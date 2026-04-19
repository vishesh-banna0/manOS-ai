"""
File: faiss_store.py

Purpose:
Stores and retrieves embeddings using FAISS.
"""

import faiss
import numpy as np


class FAISSStore:
    def __init__(self, dim: int):
        self.index = faiss.IndexFlatL2(dim)
        self.texts = []

    def add(self, embeddings, texts):
        """
        Add embeddings and corresponding texts.
        """

        vectors = np.array(embeddings).astype("float32")
        self.index.add(vectors)
        self.texts.extend(texts)

    def search(self, query_embedding, k=5):
        """
        Retrieve top-k similar chunks.
        """

        query = np.array([query_embedding]).astype("float32")
        distances, indices = self.index.search(query, k)

        results = [self.texts[i] for i in indices[0]]
        return results