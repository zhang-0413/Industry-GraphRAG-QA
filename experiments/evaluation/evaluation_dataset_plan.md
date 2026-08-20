# Stage 7.1 Evaluation Dataset Plan

## 1. 本阶段目标

阶段 7 的目标是从“功能实验”进入“系统评测”。

本阶段先完成正式评测集设计，不急着一次性写出 100-300 条问题。

当前产出：

- `evaluation_schema.json`
- `evaluation_dataset_plan.md`

核心原则：

```text
先定义评测样本格式
再定义问题分布
最后再批量构造问题和真实运行实验
```

## 2. 为什么要设计正式 schema

RAG 评测不能只保存：

```text
question
answer
```

因为 RAG 失败可能发生在两层：

```text
检索失败：没有找到正确上下文
生成失败：找到了上下文，但 LLM 没答好
```

所以一条评测样本至少要包含：

```text
question（问题）
gold_answer（标准答案）
expected_answer_points（标准答案要点）
expected_evidence（标准证据）
question_type（问题类型）
difficulty（难度）
modalities（模态）
evaluation（评测指标配置）
```

## 3. 一条正式样本长什么样

示例：

```json
{
  "sample_id": "EVAL-0001",
  "question": "What is the measured pressure of Pipeline-7A in the inspection table?",
  "question_type": "table",
  "sub_type": "pressure_value",
  "difficulty": "easy",
  "modalities": ["table"],
  "gold_answer": "The measured pressure of Pipeline-7A is 8.8 MPa.",
  "expected_answer_points": [
    "Pipeline-7A measured pressure is 8.8 MPa"
  ],
  "expected_evidence": [
    {
      "evidence_id": "E1",
      "document_id": "doc_004_pipeline_inspection",
      "file_name": "pipeline_inspection_report.pdf",
      "chunk_id": null,
      "content_type": "table",
      "chapter": "Pipeline Inspection Report",
      "section": "Pressure Records",
      "page_start": 2,
      "page_end": 2,
      "bbox": [72, 130, 540, 260],
      "evidence_text": "Measured Pressure: 8.8 MPa",
      "must_hit": true
    }
  ],
  "recommended_routes": ["bm25", "table_filter"],
  "negative_constraints": [],
  "evaluation": {
    "retrieval_metrics": [
      "hit_at_k",
      "recall_at_k",
      "mrr",
      "context_precision",
      "context_recall"
    ],
    "answer_metrics": [
      "answer_point_coverage",
      "faithfulness",
      "answer_relevance"
    ],
    "top_k_values": [1, 3, 5, 10]
  },
  "tags": ["table", "pressure", "pipeline"],
  "notes": "Table numeric lookup."
}
```

## 4. 字段解释

| 字段 | 中文含义 | 作用 |
|---|---|---|
| `sample_id` | 样本ID | 唯一标识一条问题 |
| `question` | 问题 | 用户实际提问 |
| `question_type` | 问题类型 | 用于分类统计和消融分析 |
| `sub_type` | 子类型 | 更细粒度问题标签 |
| `difficulty` | 难度 | easy / medium / hard |
| `modalities` | 模态 | text / table / image / formula |
| `gold_answer` | 标准答案 | 用于答案层评测 |
| `expected_answer_points` | 标准答案要点 | 自动或半自动评分 |
| `expected_evidence` | 标准证据 | 用于检索层评测 |
| `recommended_routes` | 推荐检索策略 | 辅助分析，不直接参与评分 |
| `negative_constraints` | 禁止出现的信息 | 用于发现幻觉或错误答案 |
| `evaluation` | 评测配置 | 指标和 TopK 配置 |
| `tags` | 标签 | 方便筛选分析 |
| `notes` | 标注说明 | 记录人工判断依据 |

## 5. 问题类型设计

正式评测集建议覆盖 10 类问题。

| question_type | 中文含义 | 主要考察 |
|---|---|---|
| `fact` | 事实题 | 单点事实检索 |
| `numeric` | 数值题 | 压力、阈值、时间、编号 |
| `entity_relation` | 实体关系题 | 谁连接谁、谁要求谁 |
| `cross_paragraph` | 跨段落题 | 同文档多个段落组合 |
| `cross_document` | 跨文档题 | 多文档证据联合 |
| `global_summary` | 全局总结题 | 多证据压缩和总结 |
| `table` | 表格题 | 表格字段、数值、比较 |
| `image` | 图片题 | 图示、安装位置、OCR/图注 |
| `causal_reasoning` | 因果题 | 现象、根因、处理动作 |
| `multi_hop` | 多跳题 | 多实体、多关系链路 |

## 6. 建议数量分布

正式版本目标：

```text
100-300 条
```

第一版建议先做 120 条。

| 类型 | 建议数量 | 难度 |
|---|---:|---|
| fact | 20 | easy |
| numeric | 15 | easy / medium |
| entity_relation | 20 | easy / medium |
| cross_paragraph | 15 | medium |
| cross_document | 15 | medium / hard |
| global_summary | 10 | hard |
| table | 15 | easy / medium |
| image | 10 | medium |
| causal_reasoning | 10 | medium / hard |
| multi_hop | 10 | hard |
| 合计 | 140 | - |

如果时间有限，先做 100 条：

| 类型 | 数量 |
|---|---:|
| fact | 15 |
| numeric | 10 |
| entity_relation | 15 |
| cross_paragraph | 10 |
| cross_document | 10 |
| global_summary | 8 |
| table | 12 |
| image | 8 |
| causal_reasoning | 7 |
| multi_hop | 5 |
| 合计 | 100 |

## 7. 难度定义

### easy

特点：

```text
单文档
单 chunk
问题关键词和原文高度一致
不需要复杂推理
```

例子：

```text
What is the design pressure of Pipeline-7A?
```

### medium

特点：

```text
单文档多 chunk 或跨段落
需要组合 2-3 条证据
可能包含表格或图片
```

例子：

```text
Which components must be inspected after an abnormal temperature report?
```

### hard

特点：

```text
跨文档
多证据
全局总结
多跳关系
需要避免噪声和幻觉
```

例子：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

## 8. 证据标注规则

`expected_evidence`（标准证据）是正式评测集最重要的字段之一。

标注规则：

1. 每条证据必须来自真实文档。
2. 尽量使用原文中的短句或完整表格行。
3. 表格证据要保留字段名和值。
4. 图片证据要来自 caption / OCR / VLM description，并保留 image_id / bbox。
5. 跨文档题必须标注多个 document_id。
6. 全局总结题可以有 3-6 条核心证据。
7. 如果证据是辅助信息，可以设置 `must_hit=false`。

推荐证据长度：

```text
20-200 字符
```

太短会误命中，太长会导致严格匹配失败。

## 9. 指标设计

### 检索层指标

| 指标 | 作用 |
|---|---|
| `Hit@K` | TopK 是否至少命中一条证据 |
| `Recall@K` | TopK 覆盖了多少标准证据 |
| `MRR` | 第一条正确证据排得靠不靠前 |
| `Context Precision` | 上下文里有多少是有效证据 |
| `Context Recall` | 标准证据有多少进入上下文 |

### 答案层指标

| 指标 | 作用 |
|---|---|
| `Answer Point Coverage` | 答案覆盖了多少标准要点 |
| `Faithfulness` | 答案是否忠实于上下文 |
| `Answer Relevance` | 答案是否回答了问题 |

### 成本指标

| 指标 | 作用 |
|---|---|
| `retrieval_latency_ms` | 检索耗时 |
| `generation_latency_ms` | 生成耗时 |
| `total_latency_ms` | 总耗时 |
| `prompt_tokens` | 输入 token |
| `completion_tokens` | 输出 token |
| `total_tokens` | 总 token |

## 10. 实验方案

正式评测集要统一跑以下方案：

| 方案 | 说明 |
|---|---|
| Vector Only | 原始向量检索 |
| BM25 Only | 关键词检索 |
| Graph Only | 图检索 |
| BM25 + Vector | 双路召回 |
| Graph + Vector | 图 + 向量 |
| Graph + Vector + BM25 | 三路召回 |
| Graph + Vector + BM25 + Rerank | 三路召回后重排序 |
| Query Router | 根据问题类型动态选择策略 |
| Multimodal Router + Filter | 表格/图片题按 content_type 过滤 |

每个方案都要跑同一套问题。

这样才能做消融实验：

```text
加 BM25 是否提升数值/术语题？
加 Graph 是否提升实体关系题？
加 Rerank 是否提升全局总结题？
Router 是否比固定策略更稳？
metadata filter 是否提升表格/图片题？
```

## 11. 数据集文件规划

建议后续目录：

```text
experiments/evaluation/
  evaluation_schema.json
  evaluation_dataset_plan.md
  datasets/
    eval_v0_20.jsonl
    eval_v1_100.jsonl
    eval_v2_300.jsonl
  documents/
    raw/
    parsed_mineru/
    assets/
  results/
    vector_only/
    bm25_only/
    graph_only/
    hybrid/
    router/
  scripts/
    validate_dataset.py
    run_retrieval_eval.py
    run_answer_eval.py
    summarize_results.py
```

## 12. 版本规划

### eval_v0_20

目标：

```text
快速验证 schema、评测脚本、指标计算是否正确
```

数量：

```text
20 条
```

建议包含：

```text
fact 3
numeric 2
entity_relation 3
cross_paragraph 2
cross_document 2
global_summary 2
table 3
image 2
causal_reasoning 1
```

### eval_v1_100

目标：

```text
作为正式 README 和简历实验结果的基础版本
```

数量：

```text
100 条
```

### eval_v2_300

目标：

```text
更完整的毕业/项目答辩版本
```

数量：

```text
300 条
```

## 13. 质量控制

正式评测集必须避免：

```text
问题答案不唯一
gold_answer 和 evidence 不一致
证据不来自原文
证据太长导致严格匹配失败
证据太短导致误命中
同一类问题过多
只考 BM25 擅长的精确关键词
只在 mini 数据集上报告最终指标
```

每条样本至少检查：

```text
question 是否清楚
gold_answer 是否可由 evidence 支持
expected_answer_points 是否覆盖答案核心
expected_evidence 是否来自真实文档
question_type 是否准确
modalities 是否准确
difficulty 是否合理
```

## 14. 下一步

进入阶段 7.2：

```text
创建 eval_v0_20.jsonl 小型正式评测集
```

目标：

```text
先写 20 条高质量样本
覆盖主要问题类型
然后写 validate_dataset.py 检查 schema 和证据字段
```

阶段 7.2 不追求数量，先追求：

```text
格式正确
证据可靠
指标可算
能真实运行
```
