# Hybrid Retrieval v0 Summary

This table compares single-route retrieval and RRF-fused hybrid retrieval at K=5.

| strategy | avg_hit_at_k | avg_recall_at_k | avg_mrr | avg_context_precision | avg_latency_ms | all_evidence_hit_samples |
| --- | --- | --- | --- | --- | --- | --- |
| bm25_vector_rrf | 1.0 | 0.9625 | 1.0 | 0.25 | 3345.14 | 19 |
| vector | 1.0 | 0.9625 | 0.9 | 0.25 | 3344.25 | 19 |
| bm25 | 1.0 | 0.9375 | 1.0 | 0.24 | 0.83 | 18 |
| bm25_vector_graph_rrf | 0.75 | 0.7125 | 0.725 | 0.19 | 5484.13 | 14 |
| graph | 0.75 | 0.7125 | 0.7 | 0.19 | 2138.99 | 14 |

Notes:

- `bm25_vector_rrf` fuses BM25 and vector candidates with Reciprocal Rank Fusion.
- `bm25_vector_graph_rrf` adds LightRAG graph-hybrid candidates to the same fusion.
- This stage does not use rerank; rerank is evaluated separately.
