# 阶段 8.2：固定切片 vs 结构感知切片实验报告

## 1. 本阶段目标

本阶段验证一个核心假设：

> Structure-aware Chunking（结构感知切片）是否一定比 Fixed Chunking（固定长度切片）更好？

注意，这个问题不能只凭直觉回答。结构感知切片看起来更合理，但它是否提升检索指标、答案指标，需要真实实验验证。

## 2. 实验脚本

新增脚本：

- `experiments/evaluation/scripts/run_chunking_ablation_v0.py`

输出目录：

- `experiments/evaluation/results/chunking_ablation_v0`

输出文件：

- `chunking_ablation_v0_records.jsonl`
- `chunking_ablation_v0_records.csv`
- `chunking_ablation_v0_summary.csv`
- `chunking_ablation_v0_chunk_stats.csv`

运行命令：

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\run_chunking_ablation_v0.py
```

## 3. 实验设置

### 对比对象

| chunking_strategy | working_dir | 说明 |
|---|---|---|
| `fixed` | `experiments/baseline_industry_mini/storage` | LightRAG 原始固定 token 切片 |
| `structure_aware` | `experiments/baseline_industry_mini/storage_structure_aware` | Markdown 标题/段落结构感知切片 |

### 问题集

使用 `eval_v0_20` 中前 15 个纯文本问题：

```text
EVAL-0001 ~ EVAL-0015
```

不纳入 EVAL-0016 ~ EVAL-0020，因为它们涉及 simulated MinerU 多模态 table/image chunk，而 fixed baseline 里没有对应多模态知识库。

### 检索策略

本阶段先比较两个最直接受 chunk 影响的检索方式：

| strategy | 说明 |
|---|---|
| `bm25` | 基于 chunk 文本关键词匹配 |
| `vector` | 基于 chunk embedding 语义检索 |

### 命中判断

本实验使用 `evidence_text`（证据文本）匹配，而不是 `chunk_id` 匹配。

原因：

```text
fixed 和 structure-aware 的 chunk 边界不同，chunk_id 不能作为公平判断标准。
```

所以本实验问的是：

> Top-K 返回的 chunk 内容中，是否真的包含标准证据文本？

## 4. Chunk 质量对比

| chunking_strategy | chunk_count | avg_chars | min_chars | max_chars | tiny_chunk_count_lt_80_chars | heading_coverage |
|---|---:|---:|---:|---:|---:|---:|
| `fixed` | 9 | 354.89 | 4 | 535 | 2 | 0.0000 |
| `structure_aware` | 11 | 278.09 | 182 | 411 | 0 | 1.0000 |

### 人话解释

`fixed` 的问题：

- 有 2 个非常短的碎片 chunk
- 最短 chunk 只有 4 个字符
- 没有 heading metadata（标题元数据）
- 有些 chunk 会截断句子或跨越多个章节

`structure_aware` 的优势：

- 没有极短碎片 chunk
- 每个 chunk 都有 heading
- chunk 更像“一个语义完整的小节”
- 更方便后续保存 chapter、section、page、content_type 等 metadata

所以从 chunk 本身质量看，结构感知切片明显更适合复杂文档工程化。

## 5. 检索结果：K=5

| chunking_strategy | retrieval_strategy | Hit@5 | Recall@5 | MRR | Context Precision | Context Recall |
|---|---|---:|---:|---:|---:|---:|
| `fixed` | `bm25` | 1.0000 | 1.0000 | 0.9222 | 0.2933 | 1.0000 |
| `structure_aware` | `bm25` | 1.0000 | 0.9500 | 1.0000 | 0.2533 | 0.9500 |
| `fixed` | `vector` | 0.9333 | 0.9167 | 0.8833 | 0.2667 | 0.9167 |
| `structure_aware` | `vector` | 0.8667 | 0.7611 | 0.7889 | 0.2267 | 0.7611 |

## 6. 关键观察

### 观察 1：结构感知切片让 BM25 Top-1 更准

在 K=1 时：

| chunking_strategy | strategy | Hit@1 | Recall@1 | MRR | Context Precision |
|---|---|---:|---:|---:|---:|
| `fixed` | `bm25` | 0.8667 | 0.7611 | 0.8667 | 0.8667 |
| `structure_aware` | `bm25` | 1.0000 | 0.8167 | 1.0000 | 1.0000 |

这说明结构感知切片能让最靠前的 chunk 更干净、更贴近问题。

人话说：

```text
structure-aware chunk 的第一名更准。
```

### 观察 2：fixed 在 K=5 的证据覆盖更高

在 K=5 时，`fixed + bm25` 的 Recall@5 达到 `1.0000`，而 `structure_aware + bm25` 是 `0.9500`。

这不代表 fixed chunk 本身更干净，而是因为 fixed chunk 更大、更混杂，有时一个 chunk 会同时包含多个证据点。

人话说：

```text
fixed chunk 因为更粗，容易“一网打尽”多个证据；
structure-aware chunk 因为更细，证据更分散，需要更好的融合和更大的候选池。
```

### 观察 3：structure-aware 的 vector 结果不如 fixed

`structure_aware + vector` 的 Recall@5 是 `0.7611`，低于 `fixed + vector` 的 `0.9167`。

可能原因：

1. 结构感知 chunk 更短，单个 chunk 包含的上下文更少。
2. 某些问题需要跨小节语义，例如 global_summary、cross_document。
3. 向量检索只看单个 chunk 相似度，未必能把多个结构化小节同时召回。
4. 当前 top_k=5 对结构感知切片可能偏小。

所以结构感知切片后，不能简单沿用固定切片的检索参数。

### 观察 4：Q015 仍然是关键失败样本

Q015 是 global_summary（全局总结）题：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

在 `structure_aware + bm25 + K=5` 下，4 条标准证据只命中 1 条，Recall@5 = 0.25。

原因是：

- 标准证据分散在多个章节
- 问题是全局总结，不是单一关键词匹配
- BM25 会优先召回关键词最密集的 chunk
- 结构感知后每个章节更独立，单个 chunk 不再包含多个主题

这说明 Q015 不是单纯切片问题，而是需要：

- hybrid retrieval
- graph retrieval
- rerank
- 更大的 candidate_top_k
- global_summary 专用 router

## 7. 本阶段结论

结构感知切片的结论不能简单写成“全面提升”。

更准确的结论是：

```text
structure-aware chunking improves chunk quality and Top-1 precision,
but may reduce Top-K evidence coverage if retrieval parameters are not adjusted.
```

中文解释：

```text
结构感知切片让 chunk 更干净、更有语义边界，
但因为证据被切得更细，Top-K 不变时，完整证据覆盖可能下降。
```

所以它的真正价值不是单独替换 fixed chunk 就能赢，而是为后续模块提供更好的基础：

- metadata filter
- Query Router
- rerank
- section-aware retrieval
- document/chapter/section grounding
- 增量索引中的稳定 chunk_id 和 content_hash

## 8. 对后续实验的影响

后续不能只比较：

```text
fixed vs structure-aware
```

还要比较：

```text
fixed + original top_k
structure-aware + original top_k
structure-aware + larger candidate_top_k
structure-aware + rerank
structure-aware + metadata filter
structure-aware + router
```

因为结构感知切片改变了检索分布。

它更适合这样的系统：

```text
先召回更多候选
-> 按标题/章节/metadata 过滤
-> rerank
-> 选最终 context
```

## 9. 可以写进 README 的结论

```markdown
### Chunking Ablation

We compared fixed-token chunking with Markdown structure-aware chunking on 15 text-only evaluation questions.

Structure-aware chunking removed tiny broken chunks and achieved full heading coverage. It improved BM25 Top-1 precision, but did not universally improve Top-5 recall under unchanged retrieval parameters. This suggests that structure-aware chunks should be combined with larger candidate pools, reranking, metadata filtering, and query routing rather than used as a drop-in replacement.
```

## 10. 下一阶段

下一阶段建议进入：

- 阶段 8.3：BM25 / Vector / Graph 单路对比

目标是弄清楚：

```text
每一种单路检索到底适合什么问题？
为什么后面必须做 hybrid retrieval？
```

