# 阶段 8.1：实验设计总表

## 1. 实验目标

本阶段的目标不是简单比较哪个方法分数最高，而是回答以下问题：

1. `BM25`（关键词检索）在编号、数值、表格、OCR/caption 问题上是否稳定有效？
2. `Vector Retrieval`（向量检索）是否能提升语义类、跨段落类问题的召回和答案忠实性？
3. `Graph Retrieval`（图检索）是否能提升实体关系、跨文档、全局总结问题？
4. `Hybrid Retrieval`（混合检索）是否比单路检索更稳？
5. `Rerank`（重排序）是否能提升 Context Precision（上下文精确率）和最终答案质量？
6. `Query Router`（查询路由器）是否比固定检索策略更适合工程系统？
7. `Metadata Filter`（元数据过滤）是否能提升 table/image 多模态问题？
8. `Structure-aware Chunking`（结构感知切片）是否优于固定长度切片？
9. `Incremental Indexing`（增量索引）是否减少重复 embedding 和重建索引成本？

最终要形成：

```text
Baseline
-> 单模块对比
-> 组合模块对比
-> 消融实验
-> 失败案例分析
-> README 实验表
```

## 2. 当前评测基础

当前已有评测集：

- `experiments/evaluation/datasets/eval_v0_20.jsonl`

当前已有评测链路：

- Retrieval Evaluation（检索评测）：`run_retrieval_eval_v0.py`
- Answer Evaluation（答案评测）：`run_answer_eval_v0.py`
- LLM Judge Evaluation（严格评测）：`run_llm_judge_eval_v0.py`
- Final Summary（最终总表）：`merge_eval_results_v0.py`

当前已有最终结果：

- `experiments/evaluation/results/final_eval_v0/final_eval_v0_summary.csv`
- `experiments/evaluation/results/final_eval_v0/final_eval_v0_summary.md`

## 3. 实验方案列表

| 编号 | 方案 | 说明 | 主要验证问题 |
|---|---|---|---|
| E0 | `bm25` | 只使用 BM25 关键词检索 | 精确匹配是否足够强 |
| E1 | `vector` | 只使用向量语义检索 | 语义检索是否更稳 |
| E2 | `graph_hybrid` | 使用 LightRAG 图谱混合检索 | 图谱是否提升实体关系问题 |
| E3 | `mix` | 使用 LightRAG mix 模式 | mix 是否比普通 graph_hybrid 更全面 |
| E4 | `bm25 + vector` | BM25 和向量召回后融合 | 双路融合是否优于单路 |
| E5 | `bm25 + vector + graph` | 三路召回融合 | 图谱加入后是否提升复杂问题 |
| E6 | `bm25 + vector + graph + rerank` | 三路召回后重排序 | rerank 是否提升最终上下文质量 |
| E7 | `router` | 规则版 Query Router | 动态选择检索策略是否有效 |
| E8 | `router + metadata filter` | 表格/图片题启用 content_type filter | 多模态过滤是否提升 table/image 问题 |
| E9 | `router + hybrid + rerank` | 复杂题走 hybrid + rerank | 复杂题增强策略是否有效 |
| E10 | `final optimized pipeline` | 最终组合方案 | 项目最终方案是否超过 baseline |

## 4. 每个方案使用的模块

| 编号 | BM25 | Vector | Graph | RRF/Fusion | Rerank | Router | Metadata Filter | Structure-aware Chunk |
|---|---|---|---|---|---|---|---|---|
| E0 | yes | no | no | no | no | no | optional | yes |
| E1 | no | yes | no | no | no | no | optional | yes |
| E2 | no | partial | yes | no | no | no | no | yes |
| E3 | no | partial | yes | no | no | no | no | yes |
| E4 | yes | yes | no | yes | no | no | optional | yes |
| E5 | yes | yes | yes | yes | no | no | optional | yes |
| E6 | yes | yes | yes | yes | yes | no | optional | yes |
| E7 | conditional | conditional | conditional | conditional | no | yes | optional | yes |
| E8 | conditional | conditional | conditional | conditional | no | yes | yes | yes |
| E9 | conditional | conditional | conditional | yes | yes | yes | yes | yes |
| E10 | yes | yes | yes | yes | yes | yes | yes | yes |

## 5. 实验假设

### H1：BM25 对精确匹配问题最强

适用问题：

- 设备编号
- 法规编号
- 事故编号
- 表格字段
- 数值
- OCR/caption 关键词

预期：

```text
bm25 在 numeric/table/image caption 类问题上 Recall@5 和 MRR 较高。
```

### H2：Vector 对语义表达更稳

适用问题：

- 同义表达
- 概念解释
- 跨段落语义关联
- 需要上下文支撑的答案生成

预期：

```text
vector 的 llm_faithfulness 和 strict_pass_rate 可能高于 bm25。
```

### H3：Graph 对实体关系和跨文档问题有潜力

适用问题：

- entity_relation
- cross_document
- multi_hop
- global_summary

预期：

```text
graph 单独不一定最高，但加入 hybrid 后可能提升复杂题。
```

### H4：Rerank 主要改善排序，不负责召回

预期：

```text
rerank 可能提升 MRR、Context Precision、Answer Point Coverage。
如果 candidate pool 没召回证据，rerank 无法凭空找回证据。
```

### H5：Router 适合工程系统

预期：

```text
router 不一定在所有指标第一，但能在不同问题类型之间取得更稳定平衡。
```

### H6：Metadata Filter 对多模态题必要

预期：

```text
table/image 问题启用 content_type filter 后，Context Precision 和 Answer Coverage 提升。
```

### H7：结构感知切片更适合复杂文档

预期：

```text
structure-aware chunking 对 cross_document、global_summary、table/image grounding 更友好。
```

## 6. 问题类型与预期最佳策略

| question_type | 预期适合策略 | 原因 |
|---|---|---|
| `fact` | `bm25` / `vector` | 事实题通常依赖实体名和定义 |
| `numeric` | `bm25` | 数值和单位需要精确匹配 |
| `entity_relation` | `graph` / `bm25` / `router` | 需要实体和关系 |
| `cross_paragraph` | `vector` / `hybrid` | 需要跨 chunk 语义聚合 |
| `cross_document` | `hybrid` / `router` | 需要多文档证据 |
| `causal_reasoning` | `hybrid + rerank` | 需要事件链和因果链 |
| `global_summary` | `graph_hybrid` / `router + rerank` | 需要全局信息覆盖 |
| `table` | `bm25 + table_filter` | 表格字段和数值精确匹配 |
| `image` | `bm25 + image_filter` | 依赖 caption/OCR/VLM description |
| `multi_hop` | `hybrid + rerank + metadata filter` | 需要跨模态、跨证据组合 |

## 7. 评测指标

### 7.1 Retrieval Metrics

| 指标 | 含义 |
|---|---|
| `Hit@K` | Top-K 中是否至少命中一条标准证据 |
| `Recall@K` | Top-K 找回了多少标准证据 |
| `MRR` | 第一条正确证据排得多靠前 |
| `Context Precision` | 返回 context 中相关 chunk 的比例 |
| `Context Recall` | context 覆盖标准证据的程度 |
| `Latency` | 检索耗时 |

### 7.2 Answer Metrics

| 指标 | 含义 |
|---|---|
| `Answer Point Coverage` | 答案覆盖了多少标准答案要点 |
| `Answer Pass Rate` | 规则评分下答案通过比例 |
| `Gold Token F1` | 生成答案与标准答案关键词重合程度 |

### 7.3 Judge Metrics

| 指标 | 含义 |
|---|---|
| `LLM Faithfulness` | 答案声明有多少被 context 支持 |
| `LLM Answer Relevance` | 答案是否回答问题并覆盖要点 |
| `Strict Pass Rate` | 要点覆盖、忠实性、相关性均过线的比例 |
| `Unsupported Claims` | 无上下文支持的声明数量 |
| `Missing Answer Points` | 缺失答案要点数量 |

### 7.4 System Metrics

| 指标 | 含义 |
|---|---|
| `Retrieval Latency` | 检索耗时 |
| `Generation Latency` | 生成答案耗时 |
| `Judge Latency` | Judge 评测耗时 |
| `Embedding Recompute Count` | 重算 embedding 的 chunk 数 |
| `Index Update Time` | 增量索引更新时间 |

## 8. 消融实验设计

最终方案假设为：

```text
Structure-aware Chunk
+ BM25
+ Vector
+ Graph
+ RRF Fusion
+ Rerank
+ Query Router
+ Metadata Filter
+ Incremental Indexing
```

消融实验：

| 编号 | 消融方案 | 对比目标 |
|---|---|---|
| A0 | Full Pipeline | 完整方案 |
| A1 | Full - BM25 | 验证 BM25 对精确匹配的贡献 |
| A2 | Full - Vector | 验证向量检索对语义召回的贡献 |
| A3 | Full - Graph | 验证图谱对关系/全局题的贡献 |
| A4 | Full - Rerank | 验证 rerank 对排序和 context precision 的贡献 |
| A5 | Full - Router | 验证动态路由是否优于固定策略 |
| A6 | Full - Metadata Filter | 验证 table/image filter 的贡献 |
| A7 | Fixed Chunk instead of Structure-aware Chunk | 验证结构感知切片是否有效 |
| A8 | Full re-index instead of Incremental Index | 验证增量索引是否降低成本 |

## 9. 预期失败案例

| 失败类型 | 可能原因 | 后续优化 |
|---|---|---|
| Recall 高但答案漏要点 | LLM 没用好 context，prompt 不够强 | 分点回答 prompt，rerank，减少噪声 |
| Context Precision 低 | Top-K 混入太多无关 chunk | metadata filter，rerank，降低 final_top_k |
| Faithfulness 低 | 答案包含无依据扩展 | 更严格 prompt，引用证据，claim 检查 |
| Answer Relevance 低 | 答案没正面回答问题 | query rewrite，answer format constraint |
| 表格题失败 | 表格 chunk 没被优先召回 | table filter，表格结构化索引 |
| 图片题失败 | caption/OCR 信息不足 | VLM description，image metadata |
| 全局总结题失败 | 证据分散，Top-K 不够 | global/hybrid 检索，更大 candidate pool |
| 多跳题失败 | 证据链不完整 | graph + vector + bm25 + rerank |
| 增量更新失败 | chunk_id/hash/version 对不上 | content_hash 校验，删除同步机制 |

## 10. 实验执行顺序

建议按以下顺序执行：

1. 固定当前 `eval_v0_20`，先跑 E0/E1/E2/E3 单路 baseline。
2. 跑 E4/E5/E6，观察融合和 rerank 是否提升。
3. 跑 E7/E8/E9，观察 router 和 metadata filter 是否提升。
4. 对比 fixed chunk 和 structure-aware chunk。
5. 进行 A0-A8 消融实验。
6. 扩展评测集到 100-300 条。
7. 重跑最终实验。
8. 整理 README 实验表和失败案例。

## 11. 当前阶段 8.1 结论

阶段 8.1 的产物是实验蓝图。

它明确了：

- 要比较哪些方案
- 每个方案验证什么假设
- 每个方案使用哪些模块
- 每种问题类型预期适合什么策略
- 使用哪些指标
- 如何做消融实验
- 失败案例要怎么分析

下一步进入：

- 阶段 8.2：固定切片 vs 结构感知切片实验

