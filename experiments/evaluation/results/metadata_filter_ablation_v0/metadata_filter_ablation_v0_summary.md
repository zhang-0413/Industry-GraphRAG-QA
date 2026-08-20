# Metadata Filter Ablation v0 Summary

## Multimodal subset at K=5

| strategy | avg_hit_at_5 | avg_recall_at_5 | avg_mrr | avg_context_precision | avg_content_type_precision | avg_candidate_space_reduction | avg_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_metadata_filtered | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9107 | 0.11 |
| vector_metadata_post_filter | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9107 | 715.38 |
| bm25_vector_rrf_metadata_filtered | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9107 | 715.5 |
| router_metadata_filter | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 0.9107 | 715.5 |
| bm25_unfiltered | 1.0 | 1.0 | 1.0 | 0.25 | 0.25 | 0.0 | 0.81 |
| vector_unfiltered | 1.0 | 1.0 | 1.0 | 0.25 | 0.25 | 0.0 | 715.14 |
| bm25_vector_rrf_unfiltered | 1.0 | 1.0 | 1.0 | 0.25 | 0.25 | 0.0 | 716.0 |

## Full dataset at K=5

| strategy | avg_hit_at_k | avg_recall_at_k | avg_mrr | avg_context_precision | avg_latency_ms |
| --- | --- | --- | --- | --- | --- |
| bm25_metadata_filtered | 1.0 | 0.9625 | 1.0 | 0.4 | 0.53 |
| bm25_unfiltered | 1.0 | 0.9375 | 1.0 | 0.24 | 0.79 |
| bm25_vector_rrf_metadata_filtered | 1.0 | 0.9625 | 1.0 | 0.4 | 715.08 |
| bm25_vector_rrf_unfiltered | 1.0 | 0.9625 | 1.0 | 0.25 | 3898.42 |
| router_metadata_filter | 1.0 | 0.9625 | 1.0 | 0.4 | 3898.32 |
| vector_metadata_post_filter | 1.0 | 0.9625 | 0.925 | 0.4 | 714.51 |
| vector_unfiltered | 1.0 | 0.9625 | 0.9 | 0.25 | 3897.57 |

Notes:

- Metadata filtering uses `content_type` to narrow the candidate space.
- Vector filtering is post-filtering in this experiment because NanoVectorDB is queried before filtering.
- The most important subset is table/image/multi-hop, where target evidence is not plain text.
