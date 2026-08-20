# 阶段 8.4：Hybrid Retrieval 对比报告

## 1. 本阶段目标

本阶段验证：

> Hybrid Retrieval（混合检索）是否比 BM25、Vector、Graph 单路检索更稳？

重点不是证明“融合一定更好”，而是看清楚：

```text
哪些检索源适合融合
哪些检索源会引入噪声
RRF 融合能解决什么问题
为什么后续还需要 Router / Rerank / Metadata Filter
```

## 2. 实验脚本

新增脚本：

- `experiments/evaluation/scripts/run_hybrid_retrieval_v0.py`

输出目录：

- `experiments/evaluation/results/hybrid_retrieval_v0`

输出文件：

- `hybrid_retrieval_v0_records.jsonl`
- `hybrid_retrieval_v0_records.csv`
- `hybrid_retrieval_v0_summary.csv`
- `hybrid_retrieval_v0_summary.md`

运行命令：

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\run_hybrid_retrieval_v0.py
```

## 3. 对比方案

| strategy | 说明 |
|---|---|
| `bm25` | 关键词精确匹配 |
| `vector` | 向量语义检索 |
| `graph` | LightRAG graph_hybrid 图谱检索 |
| `bm25_vector_rrf` | BM25 + Vector，通过 RRF 融合 |
| `bm25_vector_graph_rrf` | BM25 + Vector + Graph，通过 RRF 融合 |

本阶段不使用 rerank。

原因是：

```text
8.4 只验证融合本身
8.5 再单独验证 rerank 的贡献
```

## 4. 什么是 RRF

RRF 全称是 Reciprocal Rank Fusion（倒数排名融合）。

它不直接比较 BM25 分数、向量距离、图检索分数，因为这些分数不在同一个尺度上。

它只看每一路的 rank（排名）：

```text
RRF score = 1 / (k + rank_1) + 1 / (k + rank_2) + ...
```

比如某个 chunk：

```text
BM25 排第 1
Vector 排第 3
Graph 没召回
```

它的融合分数就来自 BM25 和 Vector 两路排名。

RRF 的优点：

- 简单
- 不需要训练
- 不需要校准不同检索器的 score
- 适合把 BM25 / Vector / Graph 这种不同来源融合

RRF 的风险：

- 它默认每一路都可信
- 如果某一路噪声很大，会把错误 chunk 往前推
- 所以不是“检索源越多越好”

## 5. 整体结果：K=5

| strategy | Hit@5 | Recall@5 | MRR | Context Precision | Latency | All Evidence Hit |
|---|---:|---:|---:|---:|---:|---:|
| `bm25_vector_rrf` | 1.0000 | 0.9625 | 1.0000 | 0.2500 | 3345.14 ms | 19 |
| `vector` | 1.0000 | 0.9625 | 0.9000 | 0.2500 | 3344.25 ms | 19 |
| `bm25` | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 0.83 ms | 18 |
| `bm25_vector_graph_rrf` | 0.7500 | 0.7125 | 0.7250 | 0.1900 | 5484.13 ms | 14 |
| `graph` | 0.7500 | 0.7125 | 0.7000 | 0.1900 | 2138.99 ms | 14 |

## 6. 关键结论

### 结论 1：BM25 + Vector 是当前最好的检索融合方案

`bm25_vector_rrf` 的 Recall@5 和 `vector` 一样是 `0.9625`，但 MRR 从 `vector` 的 `0.9000` 提升到 `1.0000`。

这说明：

```text
Vector 负责召回更多语义相关证据
BM25 负责把精确匹配证据排到更前
RRF 把两者优势合在一起
```

所以 `bm25_vector_rrf` 是当前最稳的 retrieval baseline。

### 结论 2：Graph 不能无脑加入融合

`bm25_vector_graph_rrf` 的 Recall@5 只有 `0.7125`，明显低于 `bm25_vector_rrf`。

原因不是 RRF 本身错了，而是：

```text
当前 Graph 路线在 table/image/multi-hop 多模态题上召回了大量无关 chunk。
RRF 默认每一路都可信。
Graph 的高排名噪声会挤掉 BM25/Vector 的正确结果。
```

这就是一个很典型的工程教训：

```text
Hybrid Retrieval 不是把所有结果简单混在一起。
```

### 结论 3：Graph 对 cross_document 有价值，但需要 Router 控制

按问题类型看，Graph 在 `cross_document` 上表现很好：

| question_type | strategy | Recall@5 | MRR | Context Precision |
|---|---|---:|---:|---:|
| `cross_document` | `graph` | 1.0000 | 1.0000 | 0.4000 |
| `cross_document` | `bm25_vector_graph_rrf` | 1.0000 | 1.0000 | 0.4000 |
| `cross_document` | `bm25_vector_rrf` | 1.0000 | 1.0000 | 0.4000 |
| `cross_document` | `bm25` | 0.7500 | 1.0000 | 0.3000 |

所以 Graph 不是没用，而是不适合对所有问题默认开启。

更合理的策略是：

```text
如果是 entity_relation / cross_document / global_summary：
  可以启用 Graph

如果是 numeric / table / image：
  优先 BM25 / Vector / metadata filter
```

### 结论 4：Global Summary 仍然是 hardest case

`EVAL-0015` 是全局总结题：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

所有策略在 K=5 下 Recall@5 都只有 `0.25`。

说明：

```text
这个问题不是简单融合能解决的。
```

后续需要：

- larger candidate_top_k
- source diversity（来源多样性）
- section-aware rerank（章节感知重排序）
- global summary prompt
- document-level evidence aggregation

## 7. 按题型观察

### 表格题和图片题

在 `table`、`image`、`multi_hop` 上：

| question_type | bm25_vector_rrf Recall@5 | bm25_vector_graph_rrf Recall@5 |
|---|---:|---:|
| `table` | 1.0000 | 0.0000 |
| `image` | 1.0000 | 0.0000 |
| `multi_hop` | 1.0000 | 0.0000 |

这说明 Graph 噪声对多模态题伤害明显。

多模态题应该优先使用：

- `content_type=table`
- `content_type=image`
- caption
- OCR
- metadata filter

而不是直接加入 Graph。

### 数值题

`numeric` 题上各路都能达到 Recall@5 = `1.0000`。

但 BM25 的成本最低：

```text
bm25 latency = 0.83 ms
vector latency = 3344.25 ms
graph latency = 2138.99 ms
```

所以数值题没有必要默认走重检索链路。

### 跨文档题

`cross_document` 上 Graph 和融合方案表现较好。

这说明实体和关系确实能帮助跨文档连接，但需要限定使用场景。

## 8. 对后续系统设计的影响

阶段 8.4 后，我们可以得到更明确的工程设计：

```text
默认强 baseline:
  BM25 + Vector + RRF

Graph 使用方式:
  不默认加入所有问题
  只在 Router 判断为实体关系、跨文档、全局总结时启用

多模态问题:
  优先 metadata filter
  再做 BM25 / Vector

复杂问题:
  BM25 + Vector + Graph 召回
  但需要 rerank 和 source diversity 控制噪声
```

## 9. 可以写进 README 的结论

```markdown
### Hybrid Retrieval

We evaluated BM25, vector retrieval, LightRAG graph retrieval, and RRF-based hybrid retrieval. BM25 + Vector with RRF achieved the best retrieval balance, matching vector Recall@5 (0.9625) while improving MRR from 0.9000 to 1.0000. Adding graph retrieval naively degraded performance because noisy graph candidates displaced correct table/image evidence. This shows that graph retrieval should be routed selectively rather than fused into every query.
```

## 10. 下一阶段

下一阶段建议进入：

- 阶段 8.5：Rerank 消融实验

目标是验证：

```text
Rerank 是否能把已召回的正确证据排到更前？
Rerank 是否会伤害简单问题？
什么时候应该启用 rerank？
```

