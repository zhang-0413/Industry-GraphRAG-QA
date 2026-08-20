# Incremental Index Ablation v0 Summary

| strategy | transitions | embedding_recompute_count | embedding_saved_ratio | stale_chunk_count | missing_chunk_count | query_pass_rate | measured_embedding_latency_ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| incremental_with_graph_cleanup | 3 | 2 | 0.9412 | 0 | 0 | 1.0 | 680.26 |
| full_reindex | 3 | 34 | 0.0 | 0 | 0 | 1.0 | 1485.98 |
| unstable_chunk_id | 3 | 34 | 0.0 | 34 | 34 | 1.0 | 1321.15 |
| incremental_without_delete | 3 | 2 | 0.9412 | 1 | 0 | 0.6667 | 674.64 |
| incremental_without_hash | 3 | 1 | 0.9706 | 3 | 0 | 0.6667 | 331.05 |

Notes:

- `full_reindex` is the baseline that embeds every new chunk after each update.
- `incremental_with_graph_cleanup` embeds only added/modified chunks and deletes stale chunks.
- `incremental_without_delete`, `incremental_without_hash`, and `unstable_chunk_id` are negative controls.
