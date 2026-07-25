"""Unit tests for evaluation metrics."""

import math

from backend.eval import metrics


def test_recall_and_precision_at_k():
    retrieved = [5, 3, 9, 1]
    relevant = {3, 1}

    assert metrics.recall_at_k(retrieved, relevant, 2) == 0.5
    assert metrics.recall_at_k(retrieved, relevant, 4) == 1.0
    assert metrics.precision_at_k(retrieved, relevant, 2) == 0.5
    assert metrics.precision_at_k(retrieved, relevant, 4) == 0.5


def test_hit_rate():
    assert metrics.hit_rate_at_k([1, 2, 3], {3}, 3) == 1.0
    assert metrics.hit_rate_at_k([1, 2, 3], {3}, 2) == 0.0


def test_reciprocal_rank():
    assert metrics.reciprocal_rank([9, 4, 7], {4}) == 0.5
    assert metrics.reciprocal_rank([4, 9, 7], {4}) == 1.0
    assert metrics.reciprocal_rank([1, 2], {99}) == 0.0


def test_ndcg_rewards_higher_rank():
    top = metrics.ndcg_at_k([7, 1, 2], {7}, 3)
    bottom = metrics.ndcg_at_k([1, 2, 7], {7}, 3)

    assert top == 1.0
    assert bottom < top
    assert math.isclose(bottom, (1 / math.log2(4)) / 1.0, rel_tol=1e-6)


def test_aggregate_retrieval_shape():
    results = [
        {"retrieved": [1, 2, 3], "relevant": {1}},
        {"retrieved": [4, 5, 6], "relevant": {6}},
    ]
    summary = metrics.aggregate_retrieval(results, k_values=(1, 3))

    assert summary["queries"] == 2
    assert summary["recall@1"] == 0.5
    assert summary["recall@3"] == 1.0
    assert 0 < summary["mrr"] <= 1


def test_self_containment_detects_context_leaks():
    assert metrics.is_self_contained("What is gradient descent?")
    assert not metrics.is_self_contained("According to the text, what is gradient descent?")
    assert not metrics.is_self_contained("What does the passage say about CNNs?")


def test_lexical_groundedness():
    evidence = "Backpropagation computes gradients using the chain rule."

    grounded = metrics.lexical_groundedness(
        "It computes gradients using the chain rule.", evidence
    )
    hallucinated = metrics.lexical_groundedness(
        "Transformers rely on multi-head attention mechanisms.", evidence
    )

    assert grounded > 0.7
    assert hallucinated < 0.3


def test_duplicate_rate_catches_paraphrase():
    questions = [
        "What is a convolutional neural network?",
        "What is a convolutional neural network really?",
        "Explain gradient descent optimisation.",
    ]
    assert metrics.duplicate_rate(questions) > 0
    assert metrics.duplicate_rate(["a b c d", "x y z w"]) == 0.0


def test_distribution_balance():
    assert metrics.distribution_balance(["easy", "medium", "hard"]) == 1.0
    assert metrics.distribution_balance(["medium"] * 9) < 0.4
