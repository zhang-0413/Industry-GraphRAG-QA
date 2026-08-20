# Stage 7.2 eval_v0_20 Dataset Report

## 1. 本阶段目标

本阶段创建第一版正式评测集：

```text
eval_v0_20.jsonl
```

它不是最终 100-300 条大评测集，而是一个小型正式版本，用来验证：

```text
schema 是否合理
样本字段是否完整
证据标注是否能追溯到真实 chunk
后续指标脚本是否有稳定输入
```

## 2. 新增文件

| 文件 | 作用 |
|---|---|
| `datasets/eval_v0_20.jsonl` | 20 条正式评测样本 |
| `scripts/create_eval_v0_20.py` | 从 mini 数据集和多模态样本生成 eval_v0_20 |
| `scripts/validate_dataset.py` | 校验 JSONL 格式和 schema 字段 |
| `scripts/validate_dataset_evidence.py` | 校验证据文本是否存在于真实 LightRAG chunk |
| `EVAL_V0_20_DATASET_REPORT.md` | 本阶段报告 |

## 3. 数据来源

本评测集由两部分组成：

### 3.1 文本行业文档问题

来自：

```text
experiments/baseline_industry_mini/questions.jsonl
```

共 15 条，覆盖：

```text
事实题
实体关系题
跨段落题
跨文档题
数值题
因果题
全局总结题
```

### 3.2 多模态问题

来自阶段 6.12-6.14 的模拟 MinerU 多模态 chunk：

```text
text chunk
table chunk
image chunk
```

新增 5 条，覆盖：

```text
表格数值题
表格比较题
图片定位题
文本概览题
表格 + 图片跨模态多跳题
```

## 4. 样本数量分布

总样本数：

```text
20
```

标准证据数：

```text
39
```

问题类型分布：

| question_type | 数量 |
|---|---:|
| `fact` | 4 |
| `entity_relation` | 3 |
| `cross_paragraph` | 1 |
| `numeric` | 3 |
| `causal_reasoning` | 2 |
| `cross_document` | 2 |
| `global_summary` | 1 |
| `table` | 2 |
| `image` | 1 |
| `multi_hop` | 1 |

难度分布：

| difficulty | 数量 |
|---|---:|
| `easy` | 10 |
| `medium` | 6 |
| `hard` | 4 |

模态分布：

| modality | 出现次数 |
|---|---:|
| `text` | 16 |
| `table` | 3 |
| `image` | 2 |
| `caption` | 2 |
| `ocr` | 2 |

注意：模态是多选字段，所以总数会大于样本数。

## 5. recommended_routes 分布

`recommended_routes`（推荐检索路线）不参与评分，只用于后续分析。

分布如下：

| route | 出现次数 |
|---|---:|
| `bm25` | 19 |
| `vector` | 7 |
| `graph` | 5 |
| `hybrid` | 8 |
| `hybrid_rerank` | 5 |
| `query_router` | 5 |
| `table_filter` | 3 |
| `image_filter` | 2 |

这符合当前数据集特点：

```text
术语、编号、设备名、数值较多，所以 BM25 覆盖范围很广。
跨文档、全局总结、多跳问题会推荐 hybrid / hybrid_rerank / query_router。
表格和图片问题会推荐 table_filter / image_filter。
```

## 6. 样本格式

每条样本包含：

```text
sample_id
question
question_type
sub_type
difficulty
modalities
gold_answer
expected_answer_points
expected_evidence
recommended_routes
negative_constraints
evaluation
tags
notes
```

其中 `expected_evidence`（标准证据）包含：

```text
evidence_id
document_id
file_name
chunk_id
content_type
chapter
section
page_start
page_end
bbox
evidence_text
must_hit
```

## 7. 为什么要保存 chunk_id

`chunk_id`（切片ID）不是必须一开始就有，但只要已经入库并知道 chunk，就应该保存。

作用：

```text
1. 评测时可以直接判断检索结果是否命中目标 chunk
2. 可以校验证据文本是否真的来自该 chunk
3. 可以计算 MRR（Mean Reciprocal Rank，平均倒数排名）
4. 可以分析哪个检索策略把证据排在第几名
```

本阶段为文本和多模态样本都补充了已知 `chunk_id`。

## 8. 为什么还要保存 evidence_text

只保存 `chunk_id` 不够。

原因是一个 chunk 可能包含多个事实，例如：

```text
Pipeline-7A design pressure is 10 MPa.
The alarm threshold for Pipeline-7A is 9.5 MPa.
Sensor P-210 must trigger...
```

如果只判断 chunk 命中，无法知道答案需要的具体证据是否被覆盖。

所以需要：

```text
chunk_id 判断命中哪个 chunk
evidence_text 判断命中哪条证据
```

## 9. 校验结果

运行生成命令：

```powershell
.\.venv\Scripts\python.exe experiments\evaluation\scripts\create_eval_v0_20.py
```

运行 schema 校验：

```powershell
.\.venv\Scripts\python.exe experiments\evaluation\scripts\validate_dataset.py experiments\evaluation\datasets\eval_v0_20.jsonl
```

结果：

```text
Dataset validation passed
samples: 20
evidence items: 39
```

运行证据校验：

```powershell
.\.venv\Scripts\python.exe experiments\evaluation\scripts\validate_dataset_evidence.py experiments\evaluation\datasets\eval_v0_20.jsonl
```

结果：

```text
Evidence validation passed
samples: 20
evidence items checked: 39
stores loaded: 2
chunks loaded: 14
```

这说明：

```text
eval_v0_20 不只是 JSON 格式正确；
其中带 chunk_id 的 evidence_text 也确实能在真实 LightRAG text_chunks 中找到。
```

## 10. 当前局限

当前 `eval_v0_20` 是正式评测集的第一版，但仍有局限：

1. 样本数量只有 20 条。
2. 文档规模仍然很小。
3. 多模态样本来自模拟 MinerU 输出，不是真实 PDF。
4. 问题中的关键词和文档证据仍然比较接近。
5. 当前还没有加入人工改写问题，语义泛化压力不够。
6. 当前还没有加入干扰文档，噪声压力不够。
7. 当前还没有运行完整 Recall@K / Hit@K / MRR 指标脚本。

## 11. 下一步

进入阶段 7.3：

```text
实现 retrieval evaluation 指标脚本
```

目标：

```text
基于 eval_v0_20.jsonl
计算 BM25 / Vector / Graph / Hybrid / Router 的：

Hit@K
Recall@K
MRR
Context Precision
Context Recall
Latency
```

第一版先做 retrieval-level evaluation（检索层评测），暂时不评答案生成。

原因：

```text
先确认检索证据是否找对，再评估 LLM 是否回答好。
```
