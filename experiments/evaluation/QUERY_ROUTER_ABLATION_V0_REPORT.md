# 阶段 8.6：Query Router 消融实验报告

## 1. 本阶段要学什么

本阶段学习 Query Router（查询路由器）在 RAG 系统里的作用。

前面的实验已经证明：

1. BM25（关键词检索）对编号、术语、数值题很强。
2. Vector Retrieval（向量检索）对语义相似问题更稳。
3. Graph Retrieval（图检索）能表达实体关系，但也容易带来噪声。
4. Rerank（重排序）不是默认越多越好，错误使用会伤害简单问题。

所以阶段 8.6 要验证：

固定检索策略 vs Query Router 动态选择策略，哪个更适合作为工程方案。

## 2. 通俗解释

如果没有 Query Router，系统像这样：

```text
所有问题 -> 同一套检索方式 -> 同一套 rerank -> LLM
```

问题是，不同问题需要的检索方式不同：

| 问题类型 | 更适合的路线 |
| --- | --- |
| 设备型号、规则编号、数值 | BM25 |
| 语义解释、普通事实 | Vector 或 BM25+Vector |
| 实体关系、跨文档问题 | BM25+Vector，必要时加 Graph |
| 全局总结 | 更大候选池 + Rerank |
| 表格/图片问题 | metadata filter（元数据过滤）+ 对应 content_type（内容类型） |

Query Router 的工作就是先判断问题类型，再决定走哪条 retrieval path（检索路径）。

它不是生成答案的模块，而是控制检索策略的模块。

## 3. 本实验设计

本实验复用阶段 8.5 已经真实运行得到的检索结果。

也就是说：

```text
8.5 已真实跑出各策略的 Top-5 检索结果
8.6 读取这些结果
8.6 让不同 Router 从这些策略里选择一路
8.6 对比 Router 的最终指标
```

这样做的好处是：

1. 控制变量：检索结果不变，只比较“路由选择”。
2. 速度快：不重复调用 Ollama 和 LightRAG。
3. 可解释：每道题都能看到 router 为什么选择某个 strategy（策略）。

## 4. 对比的 Router

| Router | 含义 |
| --- | --- |
| router_safe | 保守规则版：多数题用 BM25 或 BM25+Vector，只在全局总结题启用 rerank |
| router_graph_rerank | 激进图增强版：复杂题大量启用 Graph + Rerank |
| router_always_q015_rerank | 负面对照：所有问题都用 Q015 专用 reranker |
| router_oracle_by_type | 理论上界：按 question_type（问题类型）选择历史最优策略 |

注意：

`router_oracle_by_type` 不是生产可用方案，因为它使用了评测集上的历史表现来选策略。它的作用是告诉我们：如果问题类型识别和策略选择足够好，Router 最多能做到什么水平。

## 5. router_safe 的规则

`router_safe` 的核心思路是：少用复杂模块，只有确实需要时才打开。

| Route（路由） | 触发条件 | Selected Strategy（选择策略） |
| --- | --- | --- |
| exact_or_numeric | fact / numeric / 明确编号 / 设备名 / 数值 | bm25 |
| multi_evidence | cross_document / cross_paragraph / causal_reasoning / multi_hop | bm25_vector_rrf |
| table_lookup | table 问题或表格模态 | bm25_vector_rrf |
| image_lookup | image/diagram 问题或图片模态 | bm25_vector_rrf |
| global_summary | summary / across / overall / global_summary | bm25_vector_rrf_q015_rerank |

一个很关键的修正：

最初 `EVAL-0012` 被误判成精确题，因为问题里有 `IR-2024-017` 这种事故编号。但它实际是 cross_document（跨文档）题，需要多个证据。因此 router 规则调整为：

```text
先判断跨文档/多跳/复杂问题
再判断是否是精确编号题
```

这说明 Router 的规则优先级非常重要。

## 6. 整体结果

| Strategy | Hit@5 | Recall@5 | MRR | Context Precision | Latency(ms) | All Evidence Hit | Rerank Used | Graph Used |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| router_oracle_by_type | 1.0000 | 0.9875 | 1.0000 | 0.2700 | 106.75 | 19 | 1 | 0 |
| router_safe | 1.0000 | 0.9875 | 1.0000 | 0.2700 | 346.21 | 19 | 1 | 0 |
| router_graph_rerank | 1.0000 | 0.9500 | 1.0000 | 0.2500 | 871.32 | 18 | 12 | 12 |
| router_always_q015_rerank | 0.4500 | 0.3375 | 0.2683 | 0.1100 | 694.01 | 4 | 20 | 0 |

对照阶段 8.5 的固定策略：

| 固定策略 | Recall@5 | MRR | Latency(ms) |
| --- | ---: | ---: | ---: |
| bm25_vector_rrf | 0.9625 | 1.0000 | 693.83 |
| vector | 0.9625 | 0.9000 | 692.96 |
| bm25 | 0.9375 | 1.0000 | 0.81 |
| graph | 0.7125 | 0.7000 | 760.21 |

## 7. 人话解释

### 7.1 router_safe 为什么最好

`router_safe` 的 Recall@5 达到 0.9875，高于固定的 `bm25_vector_rrf` 0.9625。

原因不是它用了更复杂的检索，而是它避免了三个错误：

1. 对简单题不乱用 rerank。
2. 对精确题保留 BM25。
3. 对 Q015 这种全局总结题才启用 summary-aware rerank。

这就是 Query Router 的价值：

它不是为了“总是选择最复杂的策略”，而是为了“避免不该用的策略”。

### 7.2 router_graph_rerank 为什么不如 router_safe

`router_graph_rerank` 的 Recall@5 是 0.9500，低于 `router_safe`。

原因是它对 12 道题启用了 Graph + Rerank。

Graph 能补充实体关系，但在当前数据集上也会把一些“关系相关但不能直接回答问题”的 chunk 排进来，导致噪声增加。

所以：

```text
Graph 有用，但不能因为问题复杂就无脑加 Graph
```

Graph 更适合：

1. 实体关系查询。
2. 跨文档实体链路。
3. 全局知识网络总结。
4. 问题里实体之间的关系比原文关键词更重要的场景。

但对表格值、图片说明、具体编号和数值题，Graph 往往不是第一选择。

### 7.3 always rerank 为什么失败

`router_always_q015_rerank` 的 Recall@5 只有 0.3375。

这证明了阶段 8.5 的结论：

Rerank 不能默认全局开启。

尤其是一个为了 Q015 全局总结题调出来的 reranker，会偏向某些总结链路，把事实题、数字题、表格题的精确证据挤出 Top-5。

## 8. router_safe 的具体决策分布

| Route | Selected Strategy | Count |
| --- | --- | ---: |
| exact_or_numeric | bm25 | 10 |
| multi_evidence | bm25_vector_rrf | 5 |
| table_lookup | bm25_vector_rrf | 3 |
| image_lookup | bm25_vector_rrf | 1 |
| global_summary | bm25_vector_rrf_q015_rerank | 1 |

`router_safe` 只对 1 道题启用了 rerank，没有启用 Graph。

这说明当前小型评测集更适合“轻量稳定路线”：

```text
BM25 为主
BM25+Vector 兜底
只对全局总结题 rerank
Graph 暂时不默认进入主路
```

## 9. 唯一失败案例

`router_safe` 唯一没有全部证据命中的问题是：

| Sample | Type | Strategy | Recall@5 |
| --- | --- | --- | ---: |
| EVAL-0015 | global_summary | bm25_vector_rrf_q015_rerank | 0.75 |

它命中了 4 条标准证据中的 3 条。

这说明全局总结题仍然是当前系统短板。

后续优化方向：

1. 增大 `candidate_top_k`（候选池大小）。
2. 对 summary 题使用更稳定的真实 rerank model（重排序模型）。
3. 引入 graph community summary（图社区摘要）。
4. 用 section/chapter/document metadata 做覆盖约束，避免只集中在某一篇文档。

## 10. 对二次开发的启发

源码接入时，建议不要只加一个简单参数：

```python
enable_rerank=True
```

更合理的是：

```python
QueryParam(
    mode="hybrid",
    top_k=5,
    candidate_top_k=20,
    enable_router=True,
    router_policy="rule_v1",
    enable_rerank="router_decides",
)
```

Router 应该输出：

| 字段 | 含义 |
| --- | --- |
| route | 问题被分到哪类路由 |
| selected_strategy | 实际选择的检索策略 |
| use_bm25 | 是否使用 BM25 |
| use_vector | 是否使用向量检索 |
| use_graph | 是否使用图检索 |
| use_rerank | 是否使用重排序 |
| candidate_top_k | 候选池大小 |
| final_top_k | 最终上下文数量 |
| metadata_filter | 是否过滤 content_type / document_id / chapter |
| reason | 为什么这么选，便于调试 |

## 11. 本阶段产物

脚本：

`experiments/evaluation/scripts/run_query_router_ablation_v0.py`

结果目录：

`experiments/evaluation/results/query_router_ablation_v0/`

结果文件：

`query_router_ablation_v0_summary.csv`

`query_router_ablation_v0_records.csv`

`query_router_ablation_v0_decisions.csv`

`query_router_ablation_v0_records.jsonl`

`query_router_ablation_v0_summary.md`

## 12. 本阶段结论

Query Router 的核心价值不是追求复杂，而是选择合适。

在当前评测集上，最好的工程路线是：

```text
简单精确题 -> BM25
多证据题 -> BM25 + Vector + RRF
表格/图片题 -> metadata-aware BM25 + Vector
全局总结题 -> 扩大候选池 + rerank
Graph -> 暂时作为特定复杂关系题的候选增强，不默认进入主链路
```

这也解释了为什么工业 RAG 系统通常不会只有一个固定 `mode`，而是会有 Query Router、metadata filter、hybrid retrieval 和条件 rerank。

