# Query Router Ablation v0 Summary

| strategy | hit_at_5 | recall_at_5 | mrr | context_precision | latency_ms | all_evidence_hit_samples | rerank_used_samples | graph_used_samples |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| router_oracle_by_type | 1.0 | 0.9875 | 1.0 | 0.27 | 106.75 | 19 | 1 | 0 |
| router_safe | 1.0 | 0.9875 | 1.0 | 0.27 | 346.21 | 19 | 1 | 0 |
| router_graph_rerank | 1.0 | 0.95 | 1.0 | 0.25 | 871.32 | 18 | 12 | 12 |
| router_always_q015_rerank | 0.45 | 0.3375 | 0.2683 | 0.11 | 694.01 | 4 | 20 | 0 |

## Router Decision Counts

| router_name | route | selected_strategy | count |
| --- | --- | --- | ---: |
| router_always_q015_rerank | always_rerank | bm25_vector_rrf_q015_rerank | 20 |
| router_graph_rerank | exact_or_numeric | bm25 | 8 |
| router_graph_rerank | global_summary | bm25_vector_graph_rrf_q015_rerank | 1 |
| router_graph_rerank | graph_enriched | bm25_vector_graph_rrf_query_rerank | 11 |
| router_oracle_by_type | oracle_causal_reasoning | bm25 | 2 |
| router_oracle_by_type | oracle_cross_document | bm25_vector_rrf | 2 |
| router_oracle_by_type | oracle_cross_paragraph | bm25 | 1 |
| router_oracle_by_type | oracle_entity_relation | bm25 | 3 |
| router_oracle_by_type | oracle_fact | bm25 | 4 |
| router_oracle_by_type | oracle_global_summary | bm25_vector_rrf_q015_rerank | 1 |
| router_oracle_by_type | oracle_image | bm25 | 1 |
| router_oracle_by_type | oracle_multi_hop | bm25 | 1 |
| router_oracle_by_type | oracle_numeric | bm25 | 3 |
| router_oracle_by_type | oracle_table | bm25 | 2 |
| router_safe | exact_or_numeric | bm25 | 10 |
| router_safe | global_summary | bm25_vector_rrf_q015_rerank | 1 |
| router_safe | image_lookup | bm25_vector_rrf | 1 |
| router_safe | multi_evidence | bm25_vector_rrf | 5 |
| router_safe | table_lookup | bm25_vector_rrf | 3 |
