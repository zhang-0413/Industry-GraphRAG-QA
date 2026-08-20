# 阶段 7.3：Retrieval Evaluation 指标脚本报告

## 1. 本阶段目标

本阶段实现一个只评测“检索阶段”的脚本，不评测最终生成答案。

也就是说，脚本只回答一个问题：

> 用户问题进来后，BM25、Vector、Graph、Mix、Router 这些检索方法，能不能把标准证据 chunk 找回来？

这一步是后续评测系统的基础。因为如果检索阶段没有把证据召回，后面的 LLM 生成、Faithfulness（忠实性）、Answer Relevance（答案相关性）都很难做好。

## 2. 输入、输出与运行命令

### 输入数据

- 评测集：`experiments/evaluation/datasets/eval_v0_20.jsonl`
- 固定结构切片知识库：`experiments/baseline_industry_mini/storage_structure_aware`
- 多模态知识库：`experiments/baseline_industry_mini/storage_multimodal`

### 脚本

- `experiments/evaluation/scripts/run_retrieval_eval_v0.py`

### 运行命令

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\run_retrieval_eval_v0.py
```

运行前需要确保 Ollama 服务可用：

```powershell
ollama serve
```

本次使用的本地模型：

- LLM：`qwen2.5:3b`
- Embedding（向量模型）：`nomic-embed-text`

### 输出结果

- 明细结果：`experiments/evaluation/results/retrieval_eval_v0/retrieval_eval_v0_records.jsonl`
- 明细 CSV：`experiments/evaluation/results/retrieval_eval_v0/retrieval_eval_v0_records.csv`
- 汇总 CSV：`experiments/evaluation/results/retrieval_eval_v0/retrieval_eval_v0_summary.csv`

## 3. 评测了哪些检索方案

| strategy（检索策略） | 含义 |
|---|---|
| `bm25` | 关键词精确匹配检索，适合编号、术语、数值、表格类问题 |
| `vector` | 向量语义检索，适合语义相近但表达不同的问题 |
| `graph_hybrid` | LightRAG 的图谱混合检索，依赖实体和关系上下文 |
| `mix` | LightRAG 的混合模式，会综合知识图谱和向量上下文 |
| `router` | 规则版 Query Router（查询路由器），根据问题类型选择检索方式 |

每种方法都测试了 `K=1/3/5/10`。

## 4. 指标解释

| 指标 | 英文字段 | 人话解释 |
|---|---|---|
| Hit@K（命中率） | `hit_at_k` | Top-K 结果里只要命中任意一条标准证据，就算命中 |
| Recall@K（召回率） | `recall_at_k` | 标准证据一共有 N 条，Top-K 找回了几条 |
| MRR（平均倒数排名） | `mrr` | 第一条正确证据排得越靠前越好 |
| Context Precision（上下文精确率） | `context_precision` | 返回的 chunk 里，有多少是真正相关的 |
| Context Recall（上下文召回率） | `context_recall` | 和 Recall@K 一样，表示证据覆盖程度 |
| Latency（延迟） | `latency_ms` | 完成一次检索平均耗时，单位毫秒 |

注意：本阶段评测的是 retrieval（检索），不是 generation（生成）。所以这里不会评价答案是否写得好，只评价证据有没有被找回来。

## 5. 本次真实结果摘要

### K=5 对比结果

| strategy | Hit@5 | Recall@5 | MRR | Context Precision | Latency |
|---|---:|---:|---:|---:|---:|
| `bm25` | 1.0000 | 0.9375 | 1.0000 | 0.2400 | 0.82 ms |
| `vector` | 1.0000 | 0.9625 | 0.9000 | 0.2500 | 808.28 ms |
| `router` | 0.9500 | 0.9125 | 0.9250 | 0.3500 | 509.13 ms |
| `graph_hybrid` | 0.7500 | 0.7125 | 0.7000 | 0.1900 | 1143.07 ms |
| `mix` | 0.7500 | 0.7125 | 0.7000 | 0.1900 | 959.51 ms |

### 人话结论

1. `bm25` 在这个数据集上非常强。

   原因是我们的 20 条问题里有很多设备编号、事故编号、管线编号、阈值、表格字段，例如 `BluePump-X100`、`IR-2024-017`、`Pipeline-7A`。这些问题天然适合关键词匹配。

2. `vector` 的 Recall@5 最高。

   向量检索能找回更多语义相关 chunk，但 MRR 比 BM25 低，说明它虽然能找到证据，但第一条结果不一定总是最准确。

3. `router` 的 Context Precision 最高。

   Router 会对表格题、图片题、事实题做定向检索，所以返回的噪声更少。它不是所有指标第一，但更接近“工程上可控”的方案。

4. `graph_hybrid` 和 `mix` 在这个小数据集上没有明显赢。

   这不代表 GraphRAG 没用，而是说明：如果问题主要靠精确编号、表格字段、图片 caption、OCR 就能回答，图谱检索不一定占优势。GraphRAG 更适合实体关系复杂、跨段落、跨文档、全局总结类问题。

5. K 越大，Recall 通常越高，但 Context Precision 会下降。

   例如 `bm25` 从 K=1 到 K=10，Recall 从 0.8250 提升到 0.9875，但 Context Precision 从 1.0000 降到 0.1350。也就是说，找得更多了，但噪声也更多了。

## 6. 失败案例

在 K=5 时：

| strategy | 失败样本数 |
|---|---:|
| `bm25` | 0 |
| `vector` | 0 |
| `router` | 1 |
| `graph_hybrid` | 5 |
| `mix` | 5 |

主要失败样本：

- `EVAL-0016`：表格题，问 `Pipeline-7A` 的测量压力
- `EVAL-0017`：表格推理题，判断压力是否低于报警阈值
- `EVAL-0018`：图片题，问 `ReliefValve-RV9` 安装位置
- `EVAL-0019`：事实题，问事故后复查设备
- `EVAL-0020`：多跳题，同时需要表格和图片证据

这些失败说明：

- 表格题需要 `content_type=table` 的 metadata filter（元数据过滤）
- 图片题需要 `content_type=image`、caption（图注）、ocr_text（OCR 文本）
- 多跳题不能只靠单一路检索，需要 BM25 + Vector + Graph 融合，并可能需要 rerank（重排序）

## 7. 当前脚本的一个重要局限

当前命中判断采用两种方式：

1. `evidence_text`（证据文本）出现在返回 chunk 内容中
2. `chunk_id`（切片 ID）与标准证据标注的 chunk_id 相同

这样做的好处是：适合第一版 chunk 级 retrieval 评测。

但它也可能带来一点“偏乐观”的结果：如果一个 chunk 很大，脚本可能因为 chunk_id 相同就认为证据命中，但真实回答时模型未必能精确利用其中的细粒度证据。

后续可以拆成两个指标：

- `chunk_hit_at_k`：是否找到了正确 chunk
- `evidence_text_hit_at_k`：是否真的包含标准证据文本

## 8. 对后续阶段的作用

阶段 7.3 之后，我们已经具备了检索评测的最小闭环：

```text
评测问题
  -> 多种检索策略
  -> Top-K 证据 chunk
  -> Hit@K / Recall@K / MRR / Context Precision / Context Recall / Latency
  -> 结果表
  -> 失败案例分析
```

下一阶段可以进入：

- 阶段 7.4：实现 Answer Evaluation（答案生成评测）
- 阶段 7.5：引入 Faithfulness（忠实性）和 Answer Relevance（答案相关性）
- 阶段 7.6：把 retrieval + generation 结果合并成正式实验总表

