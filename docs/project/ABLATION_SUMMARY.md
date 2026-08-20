# Ablation Summary

本文档总结阶段 8 的实验与消融结论。所有指标来自本项目本地实验结果，不编造数据。

## 1. 最终推荐方案

```text
Structure-aware Chunking
+ BM25
+ Vector Retrieval
+ RRF
+ Query Router
+ Metadata Filter
+ Conditional Rerank
+ Conditional Graph Retrieval
+ Incremental Index
```

核心原则：

```text
BM25 + Vector + RRF 作为默认主干；
Graph、Rerank、Metadata Filter 由 Query Router 条件启用。
```

## 2. 结构感知切片

实验结果：

| 方法 | 结果 |
| --- | --- |
| fixed chunk | `heading_coverage=0`，tiny chunks=2 |
| structure-aware chunk | `heading_coverage=1`，tiny chunks=0 |

结论：

- 结构感知切片让 chunk 更可解释。
- 当前小数据集上 Recall 没有全面超过固定切片。
- 它的主要价值是 metadata、增量索引和复杂文档处理。

## 3. 单路检索

| Method | Recall@5 | MRR | Context Precision |
| --- | ---: | ---: | ---: |
| BM25 | 0.9375 | 1.0000 | 0.2400 |
| Vector | 0.9625 | 0.9000 | 0.2500 |
| Graph | 0.7125 | 0.7000 | 0.1900 |

结论：

- BM25 对精确词、编号、数值很强。
- Vector 语义召回稳定。
- Graph 不能作为默认主路。

## 4. 混合检索

| Method | Recall@5 | MRR |
| --- | ---: | ---: |
| BM25 | 0.9375 | 1.0000 |
| Vector | 0.9625 | 0.9000 |
| BM25 + Vector + RRF | 0.9625 | 1.0000 |
| BM25 + Vector + Graph + RRF | 0.7125 | 0.7250 |

结论：

- BM25 + Vector + RRF 是默认推荐。
- Graph 直接加入融合会拉低结果。

## 5. Rerank

实验结论：

- 通用 query-rerank 未超过强 baseline。
- Q015 专用 rerank 能救特定问题，但全局使用会严重伤害普通问题。
- Graph fusion 后 rerank 可以修复部分噪声。

工程决策：

```text
Rerank 是条件增强模块，不是默认全局模块。
```

## 6. Query Router

| Method | Recall@5 | MRR |
| --- | ---: | ---: |
| BM25 + Vector + RRF | 0.9625 | 1.0000 |
| router_safe | 0.9875 | 1.0000 |
| router_graph_rerank | 0.9500 | 1.0000 |

结论：

- Router Safe 提升 Recall，同时避免复杂模块过度使用。
- Aggressive Graph/Rerank 反而会下降。

## 7. 增量索引

| Method | Embedding Count | Saved Ratio | Stale Chunks |
| --- | ---: | ---: | ---: |
| full_reindex | 34 | 0 | 0 |
| incremental_with_graph_cleanup | 2 | 94.12% | 0 |
| incremental_without_delete | 2 | 94.12% | 1 |
| incremental_without_hash | 1 | 97.06% | 3 |

结论：

- 正确增量索引显著降低 embedding 成本。
- 不删除旧 chunk 会产生 stale chunks。
- 不使用 `content_hash` 会漏掉修改。

## 8. Metadata Filter

多模态子集：

| Method | Context Precision | Content Type Precision |
| --- | ---: | ---: |
| unfiltered | 0.25 | 0.25 |
| metadata filtered | 1.0 | 1.0 |

结论：

- Metadata Filter 的核心价值是降噪。
- 表格、图片、多跳问题应启用 `content_type` filter。

## 9. 总结

最终不是复杂模块越多越好，而是：

```text
Simple question -> simple retrieval
Complex question -> router decides extra modules
```

这也是本项目相对“堆功能式 RAG”的主要工程价值。
