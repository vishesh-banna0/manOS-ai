# Manos AI - Evaluation Report

Generated: 2026-07-25T11:57:27.068008  
Instance: 39  
Config: {"query_strategy": "lexical", "sample_size": 30, "llm_judge": true}

## Retrieval quality

Golden queries: **8**, index size: **8** vectors

| config | recall@1 | recall@5 | P@5 | MRR | nDCG@5 | misses@5 |
|---|---|---|---|---|---|---|
| dense_only | 0.75 | 1.0 | 0.2 | 0.875 | 0.9077 | 0 |
| hybrid | 1.0 | 1.0 | 0.2 | 1.0 | 1.0 | 0 |
| hybrid_mmr | 1.0 | 1.0 | 0.2 | 1.0 | 1.0 | 0 |

Best configuration: **hybrid** (ranked by recall@5, then MRR, nDCG@5, recall@1)

Gain over dense-only:

| metric | delta |
|---|---|
| recall@5 | +0.0000 |
| recall@1 | +0.2500 |
| mrr | +0.1250 |
| ndcg@5 | +0.0923 |

> Only 8 golden queries over 8 chunks - metrics saturate easily on a corpus this small. Index more documents before drawing conclusions.

## Generation quality

### Stored deck

| metric | value |
|---|---|
| cards | 7 |
| provenance rate | 1.0 |
| lexical groundedness (mean) | 0.9327 |
| LLM-judge groundedness (mean) | 0.6429 |
| critic groundedness (mean) | 1.0 |
| self-contained rate | 0.8571 |
| duplicate rate | 0.1429 |
| difficulty balance | 0.8571 |
| critic vs judge gap | 0.3571 |
| avg answer words | 25.0 |

> **Critic calibration:** The in-loop critic scored groundedness 1.0 but an independent judge scored 0.6429 (gap +0.36). The critic is likely over-accepting. Point CRITIC_MODEL at a stronger model than the author, and re-measure.

> Only 7 cards scored - too few to compare configurations reliably. Treat these numbers as directional.

### Agent (grounded) vs baseline (ungrounded)

| metric | delta (agent - baseline) |
|---|---|
| lexical_groundedness_mean | +0.1896 |
| judge_groundedness_mean | +0.3929 |
| self_contained_rate | -0.1429 |
| duplicate_rate | +0.1429 |
| difficulty_balance | -0.1429 |

_duplicate_rate: lower is better. All other deltas: higher is better._

> The two sides do not see identical evidence: baseline cards are judged against the single chunk they were generated from, agent cards against all the chunks they cite. That favours neither consistently, but it means small deltas are noise. Compare on a deck of 50+ cards before drawing conclusions.

## Learning effectiveness

### Scheduler simulation (identical synthetic learner)

| scheduler | reviews | review retention | final recall | recall/review | mastery | deck coverage |
|---|---|---|---|---|---|---|
| sm2 | 1567 | 0.5999 | 0.9797 | 0.03751 | 0.9833 | 1.0 |
| legacy_buggy | 1866 | 0.4812 | 0.8337 | 0.02681 | 0.9167 | 1.0 |
| fixed_1day | 4800 | 0.9663 | 0.6667 | 0.00833 | 0.6667 | 0.6667 |

_review_retention is in-session accuracy; final_recall_mean is modelled recall of the whole deck at the end. They diverge on purpose - drilling easy cards daily inflates the first while doing little for the second. fixed_1day never reached 20 of 60 cards: re-queuing everything daily exceeds the 40/day budget, so the tail of the deck starves. Its high review_retention (0.9663) is measured only on the cards it kept showing. SM-2 buys more retained knowledge per review than the legacy scheduler (0.03751 vs 0.02681) while issuing 299 fewer reviews._

| comparison | value |
|---|---|
| sm2_vs_legacy_final_recall | 0.146 |
| sm2_vs_legacy_reviews | -299 |
| sm2_vs_legacy_recall_per_review | 0.0107 |
| sm2_vs_fixed_reviews_saved | 3233 |
| sm2_vs_fixed_deck_coverage | 0.3333 |

### Real review history

| metric | value |
|---|---|
| reviews | 7 |
| window_days | 90 |
| retention_rate | 0.5714 |
| retention_short_interval | 0.5714 |
| retention_long_interval | None |
| retention_early | 0.5 |
| retention_late | 0.5 |
| retention_improvement | 0.0 |
| cards_total | 7 |
| cards_mature | 0 |
| mastery_rate | 0.0 |
| avg_ease_factor | 2.363 |
| total_lapses | 3 |
| reviews_per_card | 1.0 |
