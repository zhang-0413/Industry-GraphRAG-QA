# Single-Route Retrieval v0

This analysis compares BM25, vector retrieval, and LightRAG graph retrieval at K=5.

Graph is represented by the existing `graph_hybrid` retrieval results from `retrieval_eval_v0`.

## Overall

| route | samples | hit_at_5 | recall_at_5 | mrr | context_precision | latency_ms |
| --- | --- | --- | --- | --- | --- | --- |
| vector | 20 | 1.0 | 0.9625 | 0.9 | 0.25 | 808.28 |
| bm25 | 20 | 1.0 | 0.9375 | 1.0 | 0.24 | 0.82 |
| graph | 20 | 0.75 | 0.7125 | 0.7 | 0.19 | 1143.07 |

## By Question Type

| question_type | route | samples | hit_at_5 | recall_at_5 | mrr | context_precision |
| --- | --- | --- | --- | --- | --- | --- |
| causal_reasoning | bm25 | 2 | 1.0 | 1.0 | 1.0 | 0.3 |
| causal_reasoning | graph | 2 | 1.0 | 1.0 | 0.75 | 0.3 |
| causal_reasoning | vector | 2 | 1.0 | 1.0 | 0.75 | 0.3 |
| cross_document | graph | 2 | 1.0 | 1.0 | 1.0 | 0.4 |
| cross_document | vector | 2 | 1.0 | 1.0 | 0.75 | 0.4 |
| cross_document | bm25 | 2 | 1.0 | 0.75 | 1.0 | 0.3 |
| cross_paragraph | bm25 | 1 | 1.0 | 1.0 | 1.0 | 0.4 |
| cross_paragraph | graph | 1 | 1.0 | 1.0 | 1.0 | 0.4 |
| cross_paragraph | vector | 1 | 1.0 | 1.0 | 1.0 | 0.4 |
| entity_relation | bm25 | 3 | 1.0 | 1.0 | 1.0 | 0.2 |
| entity_relation | graph | 3 | 1.0 | 1.0 | 0.8333 | 0.2 |
| entity_relation | vector | 3 | 1.0 | 1.0 | 0.8333 | 0.2 |
| fact | bm25 | 4 | 1.0 | 1.0 | 1.0 | 0.2 |
| fact | vector | 4 | 1.0 | 1.0 | 0.875 | 0.2 |
| fact | graph | 4 | 0.75 | 0.75 | 0.75 | 0.15 |
| global_summary | bm25 | 1 | 1.0 | 0.25 | 1.0 | 0.2 |
| global_summary | graph | 1 | 1.0 | 0.25 | 1.0 | 0.2 |
| global_summary | vector | 1 | 1.0 | 0.25 | 1.0 | 0.2 |
| image | bm25 | 1 | 1.0 | 1.0 | 1.0 | 0.2 |
| image | vector | 1 | 1.0 | 1.0 | 1.0 | 0.2 |
| image | graph | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| multi_hop | bm25 | 1 | 1.0 | 1.0 | 1.0 | 0.4 |
| multi_hop | vector | 1 | 1.0 | 1.0 | 1.0 | 0.4 |
| multi_hop | graph | 1 | 0.0 | 0.0 | 0.0 | 0.0 |
| numeric | bm25 | 3 | 1.0 | 1.0 | 1.0 | 0.2 |
| numeric | graph | 3 | 1.0 | 1.0 | 1.0 | 0.2 |
| numeric | vector | 3 | 1.0 | 1.0 | 1.0 | 0.2 |
| table | bm25 | 2 | 1.0 | 1.0 | 1.0 | 0.2 |
| table | vector | 2 | 1.0 | 1.0 | 1.0 | 0.2 |
| table | graph | 2 | 0.0 | 0.0 | 0.0 | 0.0 |

## Best Route Per Sample

| sample_id | question_type | best_routes | best_recall_at_5 | best_mrr |
| --- | --- | --- | --- | --- |
| EVAL-0001 | fact | bm25 | graph | vector | 1.0 | 1.0 |
| EVAL-0002 | fact | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0003 | fact | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0004 | entity_relation | bm25 | graph | vector | 1.0 | 1.0 |
| EVAL-0005 | cross_paragraph | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0006 | entity_relation | bm25 | 1.0 | 1.0 |
| EVAL-0007 | numeric | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0008 | numeric | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0009 | numeric | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0010 | causal_reasoning | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0011 | cross_document | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0012 | cross_document | graph | 1.0 | 1.0 |
| EVAL-0013 | entity_relation | bm25 | vector | graph | 1.0 | 1.0 |
| EVAL-0014 | causal_reasoning | bm25 | 1.0 | 1.0 |
| EVAL-0015 | global_summary | bm25 | vector | graph | 0.25 | 1.0 |
| EVAL-0016 | table | bm25 | vector | 1.0 | 1.0 |
| EVAL-0017 | table | bm25 | vector | 1.0 | 1.0 |
| EVAL-0018 | image | bm25 | vector | 1.0 | 1.0 |
| EVAL-0019 | fact | bm25 | 1.0 | 1.0 |
| EVAL-0020 | multi_hop | bm25 | vector | 1.0 | 1.0 |

## Incomplete Evidence Recall

| sample_id | question_type | route | hit_evidence_count | expected_evidence_count | recall_at_5 | mrr |
| --- | --- | --- | --- | --- | --- | --- |
| EVAL-0012 | cross_document | bm25 | 1 | 2 | 0.5 | 1.0 |
| EVAL-0015 | global_summary | bm25 | 1 | 4 | 0.25 | 1.0 |
| EVAL-0015 | global_summary | graph | 1 | 4 | 0.25 | 1.0 |
| EVAL-0015 | global_summary | vector | 1 | 4 | 0.25 | 1.0 |
| EVAL-0016 | table | graph | 0 | 2 | 0.0 | 0.0 |
| EVAL-0017 | table | graph | 0 | 3 | 0.0 | 0.0 |
| EVAL-0018 | image | graph | 0 | 2 | 0.0 | 0.0 |
| EVAL-0019 | fact | graph | 0 | 1 | 0.0 | 0.0 |
| EVAL-0020 | multi_hop | graph | 0 | 4 | 0.0 | 0.0 |
