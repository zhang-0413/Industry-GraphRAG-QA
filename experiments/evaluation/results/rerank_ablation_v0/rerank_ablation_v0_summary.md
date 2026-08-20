# Rerank Ablation v0 Summary

| strategy | hit_at_5 | recall_at_5 | mrr | context_precision | all_evidence_hit_samples | rank_improved | rank_worsened | evidence_lost_after_rerank | evidence_gained_after_rerank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_vector_rrf | 1.0 | 0.9625 | 1.0 | 0.25 | 19 | 0 | 0 | 0 | 0 |
| vector | 1.0 | 0.9625 | 0.9 | 0.25 | 19 | 0 | 0 | 0 | 0 |
| bm25 | 1.0 | 0.9375 | 1.0 | 0.24 | 18 | 0 | 0 | 0 | 0 |
| bm25_vector_rrf_query_rerank | 1.0 | 0.9375 | 1.0 | 0.24 | 18 | 2 | 4 | 1 | 0 |
| bm25_vector_graph_rrf_query_rerank | 1.0 | 0.9375 | 1.0 | 0.24 | 18 | 5 | 1 | 1 | 12 |
| bm25_vector_graph_rrf | 0.75 | 0.7125 | 0.725 | 0.19 | 14 | 0 | 0 | 0 | 0 |
| graph | 0.75 | 0.7125 | 0.7 | 0.19 | 14 | 0 | 0 | 0 | 0 |
| bm25_vector_rrf_q015_rerank | 0.45 | 0.3375 | 0.2683 | 0.11 | 4 | 3 | 7 | 25 | 2 |
| bm25_vector_graph_rrf_q015_rerank | 0.4 | 0.3 | 0.2558 | 0.09 | 4 | 3 | 6 | 14 | 1 |
