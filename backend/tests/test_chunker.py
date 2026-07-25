"""
Unit tests for semantic chunking.

Embeddings are injected so these run offline and deterministically.
"""

from backend.src.ai.processing.semantic_chunker import (
    _split_sentences_with_pages,
    semantic_chunk_text,
)
from backend.src.core.config import settings


def test_page_markers_become_metadata_not_text():
    text = (
        "\n\n--- PAGE 1 ---\n\nNeural networks learn weights. "
        "They use gradients for updates.\n\n--- PAGE 2 ---\n\n"
        "Convolutions share parameters across space."
    )

    sentences = _split_sentences_with_pages(text)

    assert sentences, "expected sentences to be extracted"
    assert all("PAGE" not in sentence["text"] for sentence in sentences)
    assert {sentence["page"] for sentence in sentences} == {1, 2}


def test_chunks_split_at_semantic_boundary():
    """
    Two topics with orthogonal embeddings should not end up merged when the
    distance between them is the largest in the document.
    """
    topic_a = " ".join(["Gradients flow backward through the network."] * 4)
    topic_b = " ".join(["Photosynthesis converts light into chemical energy."] * 4)
    text = f"{topic_a} {topic_b}"

    sentences = _split_sentences_with_pages(text)
    # Orthogonal unit vectors: distance 1.0 at the topic switch, 0.0 elsewhere.
    embeddings = [
        [1.0, 0.0] if "Gradients" in sentence["text"] else [0.0, 1.0]
        for sentence in sentences
    ]

    original_target = settings.CHUNK_TARGET_WORDS
    original_min = settings.CHUNK_MIN_WORDS
    try:
        # Force the boundary to be reachable with this short fixture.
        settings.CHUNK_TARGET_WORDS = 5
        settings.CHUNK_MIN_WORDS = 1
        chunks = semantic_chunk_text(text, embeddings=embeddings)
    finally:
        settings.CHUNK_TARGET_WORDS = original_target
        settings.CHUNK_MIN_WORDS = original_min

    assert len(chunks) >= 2
    assert any("Gradients" in chunk["text"] for chunk in chunks)
    assert any("Photosynthesis" in chunk["text"] for chunk in chunks)

    # No chunk should straddle both topics.
    mixed = [
        chunk
        for chunk in chunks
        if "Gradients" in chunk["text"] and "Photosynthesis" in chunk["text"]
    ]
    assert not mixed


def test_chunks_respect_max_words():
    sentence = "This sentence has exactly eight words in it. "
    text = sentence * 200
    sentences = _split_sentences_with_pages(text)
    # Identical embeddings: no semantic breakpoints, so only the size cap acts.
    embeddings = [[1.0, 0.0]] * len(sentences)

    chunks = semantic_chunk_text(text, embeddings=embeddings)

    assert chunks
    for chunk in chunks:
        assert chunk["word_count"] <= settings.CHUNK_MAX_WORDS


def test_empty_input_returns_no_chunks():
    assert semantic_chunk_text("") == []
    assert semantic_chunk_text("    ") == []


def test_single_sentence_produces_one_chunk():
    chunks = semantic_chunk_text("A lone sentence about neural networks.")
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == 1


def test_chunk_carries_page_range():
    text = (
        "\n\n--- PAGE 3 ---\n\nAlpha content here for testing. "
        "Beta content follows immediately after."
    )
    sentences = _split_sentences_with_pages(text)
    chunks = semantic_chunk_text(text, embeddings=[[1.0, 0.0]] * len(sentences))

    assert chunks[0]["page_start"] == 3
    assert chunks[0]["page_end"] == 3
