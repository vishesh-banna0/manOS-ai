"""
File: run_eval.py

Purpose:
CLI entry point for the evaluation harness.

Usage:
    python -m backend.eval.run_eval --instance 1
    python -m backend.eval.run_eval --instance 1 --suite retrieval
    python -m backend.eval.run_eval --suite learning          # no DB content needed
    python -m backend.eval.run_eval --instance 1 --no-judge   # skip LLM judging
    python -m backend.eval.run_eval --instance 1 --queries llm

Writes a JSON report and a readable Markdown summary to backend/eval/reports/.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ..src.core.database import SessionLocal
from .datasets import build_golden_set, save_golden_set
from .generation_eval import compare_agent_vs_baseline, evaluate_stored_deck
from .learning_eval import evaluate_real_learning, run_simulation_comparison
from .retrieval_eval import run_retrieval_eval

REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def run_all(
    instance_id: Optional[int],
    suites: list[str],
    use_judge: bool = True,
    query_strategy: str = "lexical",
    sample_size: int = 30,
    gen_sample: int = 5,
) -> Dict:
    report: Dict = {
        "generated_at": datetime.utcnow().isoformat(),
        "instance_id": instance_id,
        "suites": suites,
        "config": {
            "query_strategy": query_strategy,
            "sample_size": sample_size,
            "llm_judge": use_judge,
        },
    }

    db = SessionLocal()
    try:
        if "retrieval" in suites:
            if instance_id is None:
                report["retrieval"] = {"error": "--instance is required for the retrieval suite"}
            else:
                print(f"[eval] building golden set ({query_strategy})...")
                golden = build_golden_set(
                    db, instance_id, strategy=query_strategy, sample_size=sample_size
                )
                print(f"[eval] {len(golden)} golden queries")

                if golden:
                    save_golden_set(golden, REPORTS_DIR / f"golden_set_instance_{instance_id}.json")

                print("[eval] running retrieval evaluation...")
                report["retrieval"] = run_retrieval_eval(db, instance_id, golden)

        if "generation" in suites:
            if instance_id is None:
                report["generation"] = {"error": "--instance is required for the generation suite"}
            else:
                print("[eval] scoring stored deck...")
                report["generation"] = {
                    "stored_deck": evaluate_stored_deck(db, instance_id, use_judge=use_judge)
                }
                print(
                    f"[eval] running agent vs baseline A/B on {gen_sample} chunks "
                    f"(this calls the LLM)..."
                )
                report["generation"]["ab_test"] = compare_agent_vs_baseline(
                    db, instance_id, sample_chunks=gen_sample, use_judge=use_judge
                )

        if "learning" in suites:
            print("[eval] simulating schedulers...")
            report["learning"] = {"simulation": run_simulation_comparison()}
            if instance_id is not None:
                report["learning"]["real_data"] = evaluate_real_learning(db, instance_id)
    finally:
        db.close()

    return report


# ------------------------------------------------------------------ markdown


def _table(rows: list[tuple], headers: tuple) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def to_markdown(report: Dict) -> str:
    out = [
        "# Manos AI - Evaluation Report",
        "",
        f"Generated: {report['generated_at']}  ",
        f"Instance: {report.get('instance_id')}  ",
        f"Config: {json.dumps(report.get('config', {}))}",
        "",
    ]

    # --- retrieval ---
    retrieval = report.get("retrieval")
    if retrieval:
        out += ["## Retrieval quality", ""]
        if "error" in retrieval:
            out += [f"> {retrieval['error']}", ""]
        else:
            out += [
                f"Golden queries: **{retrieval['queries']}**, index size: "
                f"**{retrieval['index_size']}** vectors",
                "",
            ]
            rows = []
            for name, payload in retrieval["configurations"].items():
                metrics = payload["metrics"]
                rows.append(
                    (
                        name,
                        metrics.get("recall@1"),
                        metrics.get("recall@5"),
                        metrics.get("precision@5"),
                        metrics.get("mrr"),
                        metrics.get("ndcg@5"),
                        metrics.get("misses_at_5"),
                    )
                )
            out += [
                _table(
                    rows,
                    ("config", "recall@1", "recall@5", "P@5", "MRR", "nDCG@5", "misses@5"),
                ),
                "",
                f"Best configuration: **{retrieval.get('best_configuration')}** "
                f"(ranked by {retrieval.get('ranked_by', 'recall@5')})",
                "",
            ]
            gain = retrieval.get("gain_over_dense_only")
            if gain:
                out += [
                    "Gain over dense-only:",
                    "",
                    _table(
                        [(k, f"{v:+.4f}") for k, v in gain.items()],
                        ("metric", "delta"),
                    ),
                    "",
                ]
            if retrieval.get("caveat"):
                out += [f"> {retrieval['caveat']}", ""]

    # --- generation ---
    generation = report.get("generation")
    if generation:
        out += ["## Generation quality", ""]
        deck = generation.get("stored_deck", {})
        if deck.get("cards"):
            rows = [
                ("cards", deck.get("cards")),
                ("provenance rate", deck.get("provenance_rate")),
                ("lexical groundedness (mean)", deck.get("lexical_groundedness_mean")),
                ("LLM-judge groundedness (mean)", deck.get("judge_groundedness_mean")),
                ("critic groundedness (mean)", deck.get("critic_groundedness_mean")),
                ("self-contained rate", deck.get("self_contained_rate")),
                ("duplicate rate", deck.get("duplicate_rate")),
                ("difficulty balance", deck.get("difficulty_balance")),
                ("critic vs judge gap", deck.get("critic_vs_judge_gap")),
                ("avg answer words", deck.get("avg_answer_words")),
            ]
            out += ["### Stored deck", "", _table(rows, ("metric", "value")), ""]
            if deck.get("critic_calibration_warning"):
                out += [f"> **Critic calibration:** {deck['critic_calibration_warning']}", ""]
            if deck.get("sample_warning"):
                out += [f"> {deck['sample_warning']}", ""]
        else:
            out += [f"> {deck.get('note', 'No deck scored.')}", ""]

        ab = generation.get("ab_test", {})
        deltas = ab.get("delta_agent_minus_baseline")
        if deltas:
            out += [
                "### Agent (grounded) vs baseline (ungrounded)",
                "",
                _table(
                    [(k, f"{v:+.4f}") for k, v in deltas.items()],
                    ("metric", "delta (agent - baseline)"),
                ),
                "",
                f"_{ab.get('note', '')}_",
                "",
                f"> {ab.get('methodology_caveat', '')}",
                "",
            ]

    # --- learning ---
    learning = report.get("learning")
    if learning:
        out += ["## Learning effectiveness", ""]
        simulation = learning.get("simulation", {})
        results = simulation.get("results", {})
        if results:
            rows = [
                (
                    name,
                    payload["total_reviews"],
                    payload["review_retention"],
                    payload["final_recall_mean"],
                    payload["recall_per_review"],
                    payload["mastery_rate"],
                    payload["deck_coverage"],
                )
                for name, payload in results.items()
            ]
            out += [
                "### Scheduler simulation (identical synthetic learner)",
                "",
                _table(
                    rows,
                    ("scheduler", "reviews", "review retention", "final recall",
                     "recall/review", "mastery", "deck coverage"),
                ),
                "",
                f"_{simulation.get('interpretation', '')}_",
                "",
            ]
            comparison = simulation.get("comparison", {})
            if comparison:
                out += [
                    _table(
                        [(k, v) for k, v in comparison.items()],
                        ("comparison", "value"),
                    ),
                    "",
                ]

        real = learning.get("real_data")
        if real and real.get("reviews"):
            rows = [(k, v) for k, v in real.items() if not isinstance(v, dict)]
            out += ["### Real review history", "", _table(rows, ("metric", "value")), ""]
        elif real:
            out += [f"> {real.get('note', '')}", ""]

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Manos AI evaluation harness")
    parser.add_argument("--instance", type=int, default=None, help="Instance id to evaluate")
    parser.add_argument(
        "--suite",
        action="append",
        choices=["retrieval", "generation", "learning", "all"],
        help="Suite to run (repeatable). Default: all",
    )
    parser.add_argument(
        "--queries",
        choices=["lexical", "llm", "both"],
        default="lexical",
        help="How to build golden retrieval queries (default: lexical, offline)",
    )
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument(
        "--gen-sample",
        type=int,
        default=5,
        help="Chunks to run the baseline generator on for the A/B (default: 5)",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip LLM-as-judge scoring (much faster)",
    )
    parser.add_argument("--out", type=str, default=None, help="Output path prefix")

    args = parser.parse_args()

    suites = args.suite or ["all"]
    if "all" in suites:
        suites = ["retrieval", "generation", "learning"]

    report = run_all(
        args.instance,
        suites,
        use_judge=not args.no_judge,
        query_strategy=args.queries,
        sample_size=args.sample_size,
        gen_sample=args.gen_sample,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    prefix = args.out or str(REPORTS_DIR / f"eval-{stamp}")

    json_path = Path(f"{prefix}.json")
    md_path = Path(f"{prefix}.md")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, default=str)

    markdown = to_markdown(report)
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(markdown)

    print()
    print(markdown)
    print()
    print(f"[eval] JSON report:     {json_path}")
    print(f"[eval] Markdown report: {md_path}")


if __name__ == "__main__":
    main()
