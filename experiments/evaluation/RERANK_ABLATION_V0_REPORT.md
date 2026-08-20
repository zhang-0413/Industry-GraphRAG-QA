# 阶段 8.5：Rerank 消融实验报告

## 1. 本阶段要解决什么问题

本阶段验证 Rerank（重排序）到底有没有价值。

在 RAG 中，Retriever（召回器）先从知识库里找一批 Candidate Chunks（候选切片），Reranker（重排序器）再对这些候选重新排序，选出最终放进 LLM Context（上下文）的 Top-K（前 K 个）。

这一步重点回答三个问题：

1. Rerank 能不能把正确证据排得更靠前？
2. Rerank 能不能修复 Graph（图检索）带来的噪声问题？
3. Rerank 什么时候会伤害简单问题？

## 2. 关键概念

Candidate Top-K（候选池大小）：召回阶段先拿多少个候选 chunk。比如先从 BM25、Vector、Graph 中各拿一些，再融合成候选池。

Final Top-K（最终上下文数量）：最终真正送给 LLM 的 chunk 数量。本实验固定为 5。

Rerank（重排序）：不重新检索新文档，只在已经召回的候选里重新排顺序。

重要结论：Rerank 只能改变顺序，不能凭空创造没有召回到的证据。如果正确 chunk 不在 Candidate Top-K 里，Rerank 救不了。

## 3. 实验设置

评测集：`eval_v0_20.jsonl`，共 20 个问题。

基础知识库：结构感知切片 + 多模态 chunk 实验中已有的工作目录。

指标：

| 指标 | 含义 |
| --- | --- |
| Hit@5（前 5 是否命中） | 前 5 个 context 中是否至少包含 1 条正确证据 |
| Recall@5（前 5 召回率） | 标准证据中有多少比例出现在前 5 |
| MRR（平均倒数排名） | 第一个正确证据越靠前，分数越高 |
| Context Precision（上下文精确率） | 前 5 个 context 中正确证据占比 |
| evidence_rank_improved（证据排名提升数） | rerank 后正确证据排名变靠前的次数 |
| evidence_rank_worsened（证据排名下降数） | rerank 后正确证据排名变靠后的次数 |
| evidence_lost_after_rerank（重排后丢失证据数） | 原本 Top-5 中有，重排后掉出 Top-5 的证据 |
| evidence_gained_after_rerank（重排后新增证据数） | 原本 Top-5 没有，重排后进入 Top-5 的证据 |

## 4. 对比方案

| Strategy（策略） | 含义 |
| --- | --- |
| bm25 | 只用 BM25 关键词检索 |
| vector | 只用向量语义检索 |
| graph | 只用 LightRAG Graph 检索 |
| bm25_vector_rrf | BM25 + Vector，用 RRF 融合，不 rerank |
| bm25_vector_graph_rrf | BM25 + Vector + Graph，用 RRF 融合，不 rerank |
| bm25_vector_rrf_query_rerank | BM25 + Vector + RRF 后，用通用 query-aware reranker 重排 |
| bm25_vector_graph_rrf_query_rerank | BM25 + Vector + Graph + RRF 后，用通用 query-aware reranker 重排 |
| bm25_vector_rrf_q015_rerank | 使用之前为 Q015 调过的局部 reranker |
| bm25_vector_graph_rrf_q015_rerank | Graph 混合后再使用 Q015 局部 reranker |

## 5. 整体结果

| Strategy | Hit@5 | Recall@5 | MRR | Context Precision | All Evidence Hit | Lost | Gained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bm25_vector_rrf | 1.0000 | 0.9625 | 1.0000 | 0.2500 | 19 | 0 | 0 |
| vector | 1.0000 | 0.9625 | 0.9000 | 0.2500 | 19 | 0 | 0 |
| bm25 | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 18 | 0 | 0 |
| bm25_vector_rrf_query_rerank | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 18 | 1 | 0 |
| bm25_vector_graph_rrf_query_rerank | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 18 | 1 | 12 |
| bm25_vector_graph_rrf | 0.7500 | 0.7125 | 0.7250 | 0.1900 | 14 | 0 | 0 |
| graph | 0.7500 | 0.7125 | 0.7000 | 0.1900 | 14 | 0 | 0 |
| bm25_vector_rrf_q015_rerank | 0.4500 | 0.3375 | 0.2683 | 0.1100 | 4 | 25 | 2 |
| bm25_vector_graph_rrf_q015_rerank | 0.4000 | 0.3000 | 0.2558 | 0.0900 | 4 | 14 | 1 |

## 6. 人话解释

### 6.1 最强的仍然是 BM25 + Vector + RRF

`bm25_vector_rrf` 的 Recall@5 是 0.9625，MRR 是 1.0000。

这说明在当前数据集上，BM25（精确词匹配）和 Vector（语义匹配）互补已经很强。RRF（Reciprocal Rank Fusion，倒数排名融合）把两路结果合并后，几乎已经把正确证据排到了最前面。

所以对这个小数据集来说，rerank 没有明显增益。

### 6.2 通用 query-aware rerank 没有超过 RRF

`bm25_vector_rrf_query_rerank` 的 Recall@5 从 0.9625 降到 0.9375。

原因是：RRF 已经把正确证据排得很好，继续用一个简单规则 reranker 重排，反而可能把本来在 Top-5 的证据挤出去。

这说明 rerank 不是“必加模块”，而是要看候选池质量和题型。

### 6.3 Graph 混合后，通用 rerank 能救一部分问题

`bm25_vector_graph_rrf` 不加 rerank 时 Recall@5 只有 0.7125。

加上 `query_rerank` 后，`bm25_vector_graph_rrf_query_rerank` 的 Recall@5 回升到 0.9375。

这说明 Graph 加进来后会带入不少实体/关系相关但不一定能直接回答问题的 chunk。通用 rerank 可以根据 query term（问题关键词）、content_type（内容类型）、multi_source（多路来源）把更相关的 chunk 拉回前面。

尤其是：

| 问题类型 | Graph+RRF 不重排 | Graph+RRF+Query Rerank | 变化 |
| --- | ---: | ---: | --- |
| table | Recall@5 = 0.0000 | Recall@5 = 1.0000 | 明显修复 |
| image | Recall@5 = 0.0000 | Recall@5 = 1.0000 | 明显修复 |
| multi_hop | Recall@5 = 0.0000 | Recall@5 = 1.0000 | 明显修复 |

但它仍然没有超过 `BM25+Vector+RRF`，因为后者本来就没有被 Graph 噪声污染。

### 6.4 Q015 局部 reranker 证明了“过拟合 rerank 很危险”

`bm25_vector_rrf_q015_rerank` 在 Q015 上把 Recall@5 从 0.25 提升到 0.75。

但是整体 Recall@5 从 0.9625 暴跌到 0.3375。

这说明一个为某个全局总结题手工调好的 reranker，会偏爱某些“看起来像总结证据”的 chunk，从而把事实题、数字题、表格题、图片题的精确证据挤掉。

这就是 rerank 会伤害简单问题的典型原因：排序规则偏了，简单问题本来靠 BM25/Vector 已经能命中，重排反而破坏原顺序。

## 7. 典型案例

### Q015：局部 reranker 确实救了全局总结题

Q015 是 global_summary（全局总结）问题。

| Strategy | Recall@5 | Context Precision |
| --- | ---: | ---: |
| bm25_vector_rrf | 0.25 | 0.20 |
| bm25_vector_rrf_query_rerank | 0.25 | 0.20 |
| bm25_vector_rrf_q015_rerank | 0.75 | 0.60 |

说明：Q015 需要覆盖多个文档和多个证据点，普通 RRF 只把一部分证据排进 Top-5。局部 reranker 更偏向“全局总结相关 chunk”，所以把更多证据拉进来了。

### 简单事实题：局部 reranker 严重伤害

例如 fact（事实题）整体：

| Strategy | Recall@5 | MRR |
| --- | ---: | ---: |
| bm25_vector_rrf | 1.0000 | 1.0000 |
| bm25_vector_rrf_q015_rerank | 0.0000 | 0.0000 |

说明：事实题需要精确实体、型号、数值或规则。BM25/Vector 已经能直接找到证据，Q015 局部 reranker 却把其他“全局链路类 chunk”排上来，导致精确证据掉出 Top-5。

## 8. 工程结论

1. Rerank 不应该默认无脑开启。
2. 对 `BM25+Vector+RRF`，当前数据集上不加 rerank 反而最好。
3. 对 `BM25+Vector+Graph+RRF`，rerank 可以缓解 Graph 噪声，但仍不如只用 BM25+Vector。
4. 对全局总结题，可以启用专门的 summary reranker，但不能把这个规则用于所有问题。
5. 对表格题、图片题、多跳题，更有效的不是普通语义 rerank，而是 metadata-aware rerank（元数据感知重排序）或 metadata filter（元数据过滤）。
6. 最合理的工程方案是 Query Router（查询路由）决定是否启用 rerank。

推荐策略：

| 问题类型 | 推荐检索策略 |
| --- | --- |
| 事实题、编号题、数值题 | BM25 或 BM25+Vector，不启用复杂 rerank |
| 语义解释题 | Vector 或 BM25+Vector |
| 实体关系题 | Graph + Vector，可启用轻量 rerank |
| 跨文档题 | BM25+Vector，必要时引入 Graph |
| 全局总结题 | 扩大 candidate_top_k，再启用 summary-aware rerank |
| 表格题 | metadata filter: content_type=table，再 BM25/Vector/rerank |
| 图片题 | metadata filter: content_type=image，再检索 caption/ocr/summary |

## 9. 对后续二次开发的影响

后续源码接入时，不建议只实现一个全局 `enable_rerank=True`。

更合理的接口应该是：

```python
QueryParam(
    mode="hybrid",
    top_k=5,
    candidate_top_k=20,
    enable_rerank=True,
    rerank_policy="router",
)
```

其中：

1. `candidate_top_k` 控制先召回多少候选。
2. `top_k` 控制最终送入 LLM 的 context 数量。
3. `enable_rerank` 控制是否启用重排。
4. `rerank_policy` 控制什么时候重排、使用哪种重排器。

## 10. 本阶段产物

脚本：

`experiments/evaluation/scripts/run_rerank_ablation_v0.py`

结果目录：

`experiments/evaluation/results/rerank_ablation_v0/`

主要结果文件：

`rerank_ablation_v0_summary.csv`

`rerank_ablation_v0_records.csv`

`rerank_ablation_v0_records.jsonl`

`rerank_ablation_v0_summary.md`

## 11. 小结

本阶段最重要的一句话：

Rerank 的价值不是“让所有问题都变强”，而是在候选池已经召回正确证据但排序不理想时，把正确证据推到最终 context 里；如果候选池不够好，或者问题本来很简单，rerank 可能没有帮助，甚至会伤害结果。

