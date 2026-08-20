# Final Evaluation v0 Summary

This table merges retrieval evaluation, answer evaluation, and LLM-judge evaluation.

| strategy | retrieval_recall_at_5 | answer_point_coverage | answer_pass_rate | llm_faithfulness | llm_answer_relevance | strict_pass_rate | retrieval_latency_ms | total_answer_latency_ms | recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vector | 0.9625 | 0.6975 | 0.5500 | 0.9425 | 0.8267 | 0.5000 | 808.28 | 3321.66 | Current best strict baseline |
| router | 0.9125 | 0.7033 | 0.6000 | 0.8633 | 0.8350 | 0.3500 | 509.13 | 3134.84 | Best candidate for engineering optimization |
| bm25 | 0.9375 | 0.6283 | 0.4500 | 0.8075 | 0.8100 | 0.3500 | 0.82 | 2597.18 | Keep as exact-match branch in hybrid/router |

Notes:

- `retrieval_recall_at_5`: evidence recall in Top-5 retrieved chunks.
- `answer_point_coverage`: rule-based coverage of expected answer points.
- `strict_pass_rate`: answer_point_coverage >= 0.8, llm_faithfulness >= 0.8, and llm_answer_relevance >= 0.8.
- `total_answer_latency_ms`: retrieval latency plus answer generation latency, excluding judge latency.
- Judge results use local `qwen2.5:3b`, so they are useful for comparison but not a final human audit.

Detailed rows are available in `final_eval_v0_summary.csv`.
