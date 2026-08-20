# Stage 8 Final Experiment Table v0

## Module-Level Conclusions

| stage | module | baseline | optimized | main_gain | engineering_decision |
| --- | --- | --- | --- | --- | --- |
| 8.2 | Structure-aware Chunking | fixed+bm25 Recall@5=1 | structure+bm25 Recall@5=0.95 | heading_coverage 0 -> 1; tiny_chunks 2 -> 0 | Keep structure-aware chunks for metadata and stable boundaries; tune top_k/rerank for recall. |
| 8.3 | Single-route Retrieval | graph Recall@5=0.7125 | vector Recall@5=0.9625; bm25 MRR=1 | BM25 is fastest/exact; Vector has highest broad recall; Graph is not a universal default. | Use BM25 and Vector as main retrieval branches; route Graph selectively. |
| 8.4 | Hybrid Retrieval | bm25 Recall@5=0.9375 | bm25+vector RRF Recall@5=0.9625 | All-evidence-hit samples 18 -> 19 | Default hybrid should be BM25+Vector+RRF, not naive Graph fusion. |
| 8.4 | Graph Fusion | bm25+vector RRF Recall@5=0.9625 | bm25+vector+graph RRF Recall@5=0.7125 | Adding Graph directly reduced retrieval quality in this dataset. | Do not put Graph into every query; use router/metadata constraints first. |
| 8.5 | Rerank | bm25+vector RRF Recall@5=0.9625 | query-rerank Recall@5=0.9375 | Rerank lost 1 evidence on already-strong BM25+Vector; Q015-only rerank Recall@5=0.3375 | Enable rerank only for routed complex/global cases, not globally. |
| 8.5 | Graph Noise Repair | bm25+vector+graph RRF Recall@5=0.7125 | graph+query-rerank Recall@5=0.9375 | Rerank gained 12 evidence after noisy Graph fusion. | If Graph is included, rerank or filtering is needed to control noise. |
| 8.6 | Query Router | fixed bm25+vector RRF Recall@5=0.9625 | router_safe Recall@5=0.9875 | Recall improved while rerank used on only 1/20 samples. | Use router_safe as current retrieval policy backbone. |
| 8.6 | Over-aggressive Graph/Rerank | router_safe Recall@5=0.9875 | router_graph_rerank Recall@5=0.95 | Graph/rerank used on 12/20 samples and underperformed. | Complex-looking questions still need conservative routing rules. |
| 8.7-8.8 | Incremental Index | full_reindex embeddings=34 | incremental embeddings=2 | Embedding saved ratio=0.9412; stale chunks=0 | Use document_id + stable chunk_id + content_hash + version with graph cleanup. |
| 8.8 | Incremental Failure Modes | without_hash stale=3 | without_delete stale=1 | Both negative controls have query_pass_rate=0.6667/0.6667 | Hash detection and delete cleanup are mandatory, not optional. |
| 8.9 | Metadata Filter | unfiltered multimodal ContextPrecision=0.25 | filtered ContextPrecision=1 | Candidate space reduction=0.9107; content type precision=1 | For table/image/multimodal queries, filter by content_type before final context. |
| 7 | Answer/Judge Baseline | bm25 strict_pass=0.35 | vector strict_pass=0.5 | router has best answer coverage=0.7033 but more unsupported claims than vector. | Retrieval optimization must be verified with answer and faithfulness metrics. |

## Final Optimized Pipeline

| component | final_choice | reason |
| --- | --- | --- |
| chunking | structure-aware chunking | Preserves section metadata, removes tiny broken chunks, supports stable chunk_id/hash for incremental index. |
| default retrieval | BM25 + Vector + RRF | Best stable retrieval backbone in current experiments: Recall@5 0.9625, MRR 1.0. |
| query router | router_safe | Recall@5 0.9875 with only one routed rerank call; avoids overusing Graph/rerank. |
| graph retrieval | selective, not default | Graph alone and naive graph fusion underperformed; use for entity/global cases after routing. |
| rerank | conditional | Useful for noisy Graph/global-summary cases, harmful when applied blindly. |
| metadata filter | enable for table/image/multi-hop | Multimodal Context Precision improved from 0.25 to 1.0 while Recall@5 stayed 1.0. |
| incremental index | chunk-level diff with graph cleanup | Embedding recompute count dropped from 34 to 2 with no stale chunks. |

## Recommended Pipeline

```text
Document -> MinerU/Parser -> Structure-aware Chunk
-> document_id/chunk_id/content_hash/version
-> BM25 Index + Vector Store + selective Graph Store
-> Query Router
-> Metadata Filter for table/image
-> BM25 + Vector + RRF by default
-> Conditional Graph and Conditional Rerank
-> Final Top-K Context -> LLM Answer
-> Retrieval/Answer/Faithfulness Evaluation
```
