# 阶段 8.3：BM25 / Vector / Graph 单路对比报告

## 1. 本阶段目标

本阶段回答一个问题：

> BM25、Vector、Graph 三种单路检索分别适合什么问题？

这一步是后续 Hybrid Retrieval（混合检索）和 Query Router（查询路由器）的基础。

如果不知道每一路检索的优势和短板，就无法合理设计：

```text
什么时候用 BM25
什么时候用 Vector
什么时候用 Graph
什么时候做融合
什么时候交给 Router 动态选择
```

## 2. 实验脚本

新增分析脚本：

- `experiments/evaluation/scripts/analyze_single_route_retrieval_v0.py`

该脚本不重新调用模型，而是读取阶段 7.3 已经真实运行得到的检索明细：

- `experiments/evaluation/results/retrieval_eval_v0/retrieval_eval_v0_records.csv`

输出目录：

- `experiments/evaluation/results/single_route_retrieval_v0`

输出文件：

- `single_route_overall.csv`
- `single_route_by_question_type.csv`
- `single_route_winners.csv`
- `single_route_failures.csv`
- `single_route_retrieval_v0_summary.md`

## 3. 对比路线

| route | 对应来源 | 说明 |
|---|---|---|
| `bm25` | `bm25` | 独立关键词检索 |
| `vector` | `vector` | 独立向量语义检索 |
| `graph` | `graph_hybrid` | 使用 LightRAG 的图谱检索路线代表 Graph |

说明：

当前 LightRAG 的图检索通常不是完全孤立的纯 graph query，而是会结合实体、关系和相关 chunk 构建上下文。因此本报告中的 `graph` 使用 `graph_hybrid` 结果代表图谱路线。

## 4. 整体结果：K=5

| route | samples | Hit@5 | Recall@5 | MRR | Context Precision | Latency |
|---|---:|---:|---:|---:|---:|---:|
| `vector` | 20 | 1.0000 | 0.9625 | 0.9000 | 0.2500 | 808.28 ms |
| `bm25` | 20 | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 0.82 ms |
| `graph` | 20 | 0.7500 | 0.7125 | 0.7000 | 0.1900 | 1143.07 ms |

## 5. 人话结论

### 结论 1：Vector 的整体 Recall@5 最高

`vector` 的 Recall@5 是 `0.9625`，是三者中最高。

说明：

```text
向量检索更容易把语义相关证据找回来。
```

但它的 MRR 是 `0.9000`，低于 BM25 的 `1.0000`。

这说明：

```text
Vector 能找回证据，但第一名不一定总是最准。
```

### 结论 2：BM25 速度最快，排序最靠前

`bm25` 的平均检索延迟只有 `0.82 ms`，而 `vector` 是 `808.28 ms`，`graph` 是 `1143.07 ms`。

BM25 的 MRR 是 `1.0000`，说明只要命中，正确证据通常排在第一。

这说明：

```text
BM25 非常适合设备编号、法规编号、事故编号、数值、表格字段、OCR/caption 关键词。
```

### 结论 3：Graph 当前整体不占优，但在跨文档题上有效

`graph` 的总体 Recall@5 只有 `0.7125`，低于 BM25 和 Vector。

但按问题类型看，Graph 在 `cross_document` 上表现很好：

| question_type | route | Recall@5 | MRR | Context Precision |
|---|---|---:|---:|---:|
| `cross_document` | `graph` | 1.0000 | 1.0000 | 0.4000 |
| `cross_document` | `vector` | 1.0000 | 0.7500 | 0.4000 |
| `cross_document` | `bm25` | 0.7500 | 1.0000 | 0.3000 |

这说明 Graph 的价值不在所有问题上平均领先，而是在实体关系、跨文档连接上有潜力。

### 结论 4：Graph 对 table/image/multi-hop 多模态题失败明显

Graph 在以下题型上表现差：

| question_type | graph Recall@5 |
|---|---:|
| `table` | 0.0000 |
| `image` | 0.0000 |
| `multi_hop` | 0.0000 |

原因可能是：

1. 表格字段不一定被抽成稳定实体/关系。
2. 图片信息主要来自 caption/OCR/VLM description，不一定进入 graph 结构。
3. 多模态题需要 metadata filter，而不是只靠实体关系。
4. 当前图谱构建还没有针对 table/image 节点建模。

所以：

```text
GraphRAG 不等于天然解决多模态问题。
```

多模态 RAG 还需要：

- `content_type=table`
- `content_type=image`
- caption
- OCR
- VLM description
- metadata filter
- 多模态 chunk schema

## 6. 按问题类型总结

| question_type | 更适合的单路 | 说明 |
|---|---|---|
| `fact` | `bm25` / `vector` | 实体名明确，BM25 很稳，Vector 也能召回 |
| `numeric` | `bm25` | 数字和单位精确匹配，BM25 成本最低 |
| `entity_relation` | `bm25` / `graph` / `vector` | 当前三路都能召回，但 BM25 排序最稳 |
| `cross_paragraph` | 三路都可 | 当前样本太少，三路都命中 |
| `cross_document` | `graph` / `vector` | Graph 可以利用实体关系连接跨文档证据 |
| `causal_reasoning` | 三路都可，但需 rerank | 三路 Recall 都高，但最终答案仍可能漏要点 |
| `global_summary` | 单路都不够 | 三路 Recall@5 都只有 0.25 |
| `table` | `bm25` / `vector` | Graph 失败，需要 table filter |
| `image` | `bm25` / `vector` | Graph 失败，需要 caption/OCR/image filter |
| `multi_hop` | `bm25` / `vector` 起步，后续需 hybrid | Graph 当前失败，后续需要融合和 metadata filter |

## 7. 失败案例

### EVAL-0015：全局总结题

问题：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

三路都失败：

| route | Recall@5 |
|---|---:|
| `bm25` | 0.25 |
| `vector` | 0.25 |
| `graph` | 0.25 |

说明：

```text
global_summary 不是单路检索能轻松解决的问题。
```

它需要：

- 更大的 candidate_top_k
- BM25 + Vector + Graph 融合
- Rerank
- 全局总结专用 prompt
- 可能还需要按 document / section 聚合上下文

### EVAL-0016 / EVAL-0017：表格题

Graph Recall@5 为 `0.0`。

说明：

```text
表格题不能只靠图谱实体关系，需要 table chunk 和 metadata filter。
```

### EVAL-0018：图片题

Graph Recall@5 为 `0.0`。

说明：

```text
图片题依赖 caption/OCR/VLM description，不能假设 Graph 自动理解图像。
```

## 8. 对 Hybrid Retrieval 的启发

本实验说明三路检索互补：

```text
BM25:
  快，适合精确词、编号、数值、表格字段

Vector:
  召回强，适合语义相似、答案忠实性较稳

Graph:
  对跨文档、实体关系有潜力，但不适合直接处理表格/图片
```

因此后续 Hybrid Retrieval 不应该是简单拼接，而应该：

```text
1. BM25 召回精确证据
2. Vector 召回语义证据
3. Graph 召回实体关系证据
4. RRF 融合 rank
5. 按 chunk_id 去重
6. 对复杂题 rerank
7. 对 table/image 题使用 metadata filter
```

## 9. 可以写进 README 的结论

```markdown
### Single-Route Retrieval Analysis

We compared BM25, vector retrieval, and LightRAG graph retrieval at K=5. Vector retrieval achieved the highest overall Recall@5 (0.9625), while BM25 achieved the best MRR (1.0000) and the lowest latency (0.82 ms). Graph retrieval was not the strongest overall, but it performed well on cross-document questions, suggesting that graph retrieval is most useful when entity and relation traversal is required. Table and image questions still require metadata-aware retrieval rather than graph retrieval alone.
```

## 10. 下一阶段

下一阶段建议进入：

- 阶段 8.4：Hybrid Retrieval 对比

目标是比较：

```text
BM25
Vector
Graph
BM25 + Vector
BM25 + Vector + Graph
BM25 + Vector + Graph + Rerank
```

看看融合是否真的解决单路检索的短板。

