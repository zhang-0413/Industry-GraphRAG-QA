# 阶段 8.10：最终优化方案总实验表

## 1. 本阶段做了什么

本阶段把阶段 8.2 到 8.9 的实验结果合并成一张总表，用来回答：

```text
最终项目应该保留哪些模块？
哪些模块应该默认开启？
哪些模块只能按问题类型条件开启？
哪些结果可以写进 README 和简历？
```

新增合并脚本：

`experiments/evaluation/scripts/merge_stage8_final_table_v0.py`

输出目录：

`experiments/evaluation/results/stage8_final_table_v0/`

## 2. 最终模块级结论

| 阶段 | 模块 | Baseline（基线） | Optimized（优化后） | 主要收益 | 工程决策 |
| --- | --- | --- | --- | --- | --- |
| 8.2 | Structure-aware Chunking（结构感知切片） | fixed+bm25 Recall@5=1.0 | structure+bm25 Recall@5=0.95 | heading_coverage 0 -> 1；tiny chunks 2 -> 0 | 保留结构感知切片，但不要声称它在当前小数据集 Recall 全面超过固定切片 |
| 8.3 | Single-route Retrieval（单路检索） | graph Recall@5=0.7125 | vector Recall@5=0.9625；bm25 MRR=1.0 | BM25 精确、Vector 召回强、Graph 不适合作默认路线 | 主检索用 BM25 + Vector，Graph 条件启用 |
| 8.4 | Hybrid Retrieval（混合检索） | bm25 Recall@5=0.9375 | bm25+vector RRF Recall@5=0.9625 | 全证据命中样本 18 -> 19 | 默认混合检索采用 BM25 + Vector + RRF |
| 8.4 | Graph Fusion（图融合） | bm25+vector RRF Recall@5=0.9625 | bm25+vector+graph RRF Recall@5=0.7125 | 直接加入 Graph 反而降低结果 | Graph 不能无脑加入全部问题 |
| 8.5 | Rerank（重排序） | bm25+vector RRF Recall@5=0.9625 | query-rerank Recall@5=0.9375 | 通用 rerank 没有超过强基线，且丢 1 条证据 | Rerank 只能条件启用 |
| 8.5 | Graph Noise Repair（图噪声修复） | graph fusion Recall@5=0.7125 | graph+query-rerank Recall@5=0.9375 | noisy Graph fusion 后 rerank 新拉回 12 条证据 | 如果启用 Graph，通常需要 rerank/filter 控噪 |
| 8.6 | Query Router（查询路由） | fixed bm25+vector RRF Recall@5=0.9625 | router_safe Recall@5=0.9875 | 只对 1/20 问题启用 rerank，仍提升 Recall | 当前主策略采用 router_safe |
| 8.6 | Over-aggressive Graph/Rerank（过度图检索/重排） | router_safe Recall@5=0.9875 | router_graph_rerank Recall@5=0.95 | 12/20 问题启用 Graph/rerank 后反而下降 | 复杂模块要谨慎路由 |
| 8.7-8.8 | Incremental Index（增量索引） | full_reindex embeddings=34 | incremental embeddings=2 | embedding 节省 94.12%，stale chunks=0 | 使用 document_id + chunk_id + content_hash + version |
| 8.8 | Incremental Failure Modes（增量失败模式） | without_hash stale=3 | without_delete stale=1 | 不看 hash / 不删除都会产生脏数据 | hash 检测和 delete cleanup 必须做 |
| 8.9 | Metadata Filter（元数据过滤） | unfiltered multimodal ContextPrecision=0.25 | filtered ContextPrecision=1.0 | 候选空间减少 91.07%，类型精确率 1.0 | table/image/multi-hop 问题启用 content_type filter |
| 7 | Answer/Judge Baseline（答案与裁判评测） | bm25 strict_pass=0.35 | vector strict_pass=0.5 | router answer coverage=0.7033，但 unsupported claims 更多 | 检索提升必须继续用答案质量和忠实性验证 |

## 3. 当前推荐的最终优化方案

不是“所有模块全部打开”，而是：

```text
结构感知切片
+ BM25
+ Vector Retrieval
+ RRF 融合
+ Query Router
+ Metadata Filter
+ 条件 Rerank
+ 条件 Graph Retrieval
+ 增量索引
```

推荐链路：

```text
Document
-> MinerU / Parser
-> Structure-aware Chunk
-> document_id / chunk_id / content_hash / version
-> BM25 Index + Vector Store + selective Graph Store
-> Query Router
-> Metadata Filter for table/image
-> BM25 + Vector + RRF by default
-> Conditional Graph and Conditional Rerank
-> Final Top-K Context
-> LLM Answer
-> Retrieval / Answer / Faithfulness Evaluation
```

## 4. 最终策略表

| 问题类型 | 推荐策略 | 是否 Graph | 是否 Rerank | 是否 Metadata Filter |
| --- | --- | --- | --- | --- |
| fact（事实题） | BM25 或 BM25+Vector | 否 | 否 | 通常否 |
| numeric（数值题） | BM25 | 否 | 否 | 表格数值题可用 table filter |
| entity_relation（实体关系题） | BM25+Vector，必要时 Graph | 条件启用 | 条件启用 | 通常否 |
| cross_paragraph（跨段落题） | BM25+Vector+RRF | 通常否 | 通常否 | 通常否 |
| cross_document（跨文档题） | BM25+Vector+RRF，必要时 Graph | 条件启用 | 条件启用 | 可按 document/chapter 过滤 |
| causal_reasoning（因果题） | BM25+Vector+RRF | 条件启用 | 条件启用 | 通常否 |
| global_summary（全局总结题） | 扩大 candidate_top_k + summary-aware rerank | 条件启用 | 是 | 可按文档覆盖约束 |
| table（表格题） | content_type=table + BM25/Vector | 否 | 通常否 | 是 |
| image（图片题） | content_type=image + caption/OCR/VLM description 检索 | 否 | 通常否 | 是 |
| multi_hop（多跳/跨模态题） | table/image filter + BM25+Vector+RRF | 条件启用 | 条件启用 | 是 |

## 5. 为什么最终不是 Graph 全开

从实验看：

```text
graph Recall@5 = 0.7125
bm25+vector RRF Recall@5 = 0.9625
bm25+vector+graph RRF Recall@5 = 0.7125
```

这说明 Graph 在当前小数据集里并没有作为通用检索路线获胜。

原因是：

1. Graph 会返回实体/关系相关内容，但相关不等于能直接回答问题。
2. 表格和图片证据不一定能被图谱结构很好表达。
3. 直接把 Graph 候选和 BM25/Vector 候选融合，会把噪声推入 Top-K。

所以最终设计是：

```text
Graph 是增强模块，不是默认主路。
```

## 6. 为什么最终不是 Rerank 全开

从实验看：

```text
bm25+vector RRF Recall@5 = 0.9625
bm25+vector RRF + query-rerank Recall@5 = 0.9375
Q015 专用 rerank 全局套用 Recall@5 = 0.3375
```

这说明 rerank 的使用条件很重要。

Rerank 适合：

```text
正确证据已经在 candidate pool 里
但没有排进 final top_k
```

Rerank 不适合：

```text
简单事实题
编号题
数值题
候选池本来已经很准的问题
```

## 7. 为什么保留结构感知切片

结构感知切片在当前 15 个文本问题上的 Recall@5 没有全面超过固定切片：

```text
fixed+bm25 Recall@5 = 1.0
structure+bm25 Recall@5 = 0.95
```

但它仍然应该保留。

原因不是单次 Recall 更高，而是工程价值更强：

```text
heading_coverage: 0 -> 1
tiny chunks: 2 -> 0
chunk 边界更稳定
metadata 更完整
更适合 document_id/chunk_id/content_hash/version
更适合 table/image/chapter/section filter
```

所以 README 里不能写：

```text
结构感知切片全面提升 Recall
```

应该写：

```text
结构感知切片提升了 chunk 语义完整性、元数据可追踪性和增量索引稳定性；在当前小规模实验中需结合 top_k、router、rerank 进一步优化召回。
```

## 8. 可以写进 README 的核心结果

| 能力 | 结果 |
| --- | --- |
| BM25+Vector+RRF | Recall@5 从 BM25 的 0.9375 提升到 0.9625 |
| Query Router | Recall@5 提升到 0.9875，且只对 1/20 问题启用 rerank |
| Metadata Filter | 多模态子集 Context Precision 从 0.25 提升到 1.0 |
| Incremental Index | embedding 重算量从 34 降到 2，节省 94.12% |
| Rerank 消融 | 证明 rerank 不能全局开启，错误 rerank 会使 Recall@5 降到 0.3375 |
| Graph 消融 | 证明 Graph 不能无脑融合，需要 Query Router 控制 |

## 9. 当前最终方案的限制

这些实验结果必须诚实说明限制：

1. 当前正式评测集只有 20 道题。
2. 多模态数据是小规模模拟 MinerU 输出，不是真实大规模行业 PDF。
3. Rerank 是本地简易规则/局部 reranker，不是真实 cross-encoder rerank model。
4. 增量索引目前是实验层原型，还没有完整接入 LightRAG 核心入库流程。
5. Graph 在当前数据集效果一般，不代表 GraphRAG 没价值，而是说明图谱检索需要更好的实体抽取、社区摘要和路由策略。
6. 本地 Ollama 延迟受 warm-up、缓存和机器状态影响，延迟指标只作参考。

## 10. 当前 README 推荐表述

可以写：

```text
基于 LightRAG 实现面向复杂行业文档的多模态 GraphRAG 知识库问答原型，
扩展结构感知切片、BM25+Vector 混合检索、RRF 融合、Query Router、metadata filter、
条件 rerank 和增量索引评测模块。
在 20 条自建评测集上，Query Router 检索 Recall@5 达到 0.9875；
多模态 table/image 子集 Context Precision 从 0.25 提升到 1.0；
增量索引实验中 embedding 重算量从 34 降至 2，节省 94.12%。
```

不要写：

```text
GraphRAG 全面超过传统 RAG
Rerank 一定提升效果
结构感知切片一定提升 Recall
系统已经达到生产级
```

## 11. 本阶段产物

合并脚本：

`experiments/evaluation/scripts/merge_stage8_final_table_v0.py`

结果目录：

`experiments/evaluation/results/stage8_final_table_v0/`

结果文件：

`stage8_final_experiment_table.csv`

`stage8_final_recommendation.csv`

`stage8_final_experiment_table.md`

阶段报告：

`experiments/evaluation/STAGE8_FINAL_OPTIMIZED_EXPERIMENT_TABLE_V0.md`

## 12. 阶段 8 总结

阶段 8 最终得到的不是一个“最复杂方案”，而是一个更像真实工程系统的策略：

```text
默认轻量、精确、稳定；
复杂问题再逐步打开 Graph、Rerank、Metadata Filter；
文档更新时只处理变化 chunk；
所有优化都必须用 retrieval + answer + faithfulness + cost 指标验证。
```

这就是从“能跑的 RAG demo”走向“可以写进简历的二次开发项目”的关键区别。

