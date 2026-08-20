# 阶段 7.5：Faithfulness 与 Answer Relevance 严格评测报告

## 1. 本阶段目标

阶段 7.4 已经实现了 Answer Evaluation（答案生成评测），但其中的 `faithfulness_proxy` 和 `answer_relevance_proxy` 仍然是规则版代理指标。

阶段 7.5 的目标是进一步接近 RAGAS 的评测思想：

```text
generated answer
  -> 拆成 factual claims（事实声明）
  -> 判断每个 claim 是否被 context 支持
  -> 判断答案是否真正回答 question
  -> 判断是否覆盖 expected_answer_points
```

这一步比简单关键词匹配更严格。

## 2. 新增脚本

- `experiments/evaluation/scripts/run_llm_judge_eval_v0.py`

它读取阶段 7.4 生成的答案结果：

- `experiments/evaluation/results/answer_eval_v0/answer_eval_v0_records.jsonl`

然后重建每条答案对应的 context，再调用本地 Ollama 模型作为 LLM Judge（评审模型）。

## 3. 运行命令

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\run_llm_judge_eval_v0.py
```

本次使用：

| 项目 | 值 |
|---|---|
| Judge model | `qwen2.5:3b` |
| Host | `http://localhost:11434` |
| Input answers | 60 |
| Strategies | `bm25`, `vector`, `router` |

输出文件：

- `experiments/evaluation/results/llm_judge_eval_v0/llm_judge_eval_v0_records.jsonl`
- `experiments/evaluation/results/llm_judge_eval_v0/llm_judge_eval_v0_records.csv`
- `experiments/evaluation/results/llm_judge_eval_v0/llm_judge_eval_v0_summary.csv`

## 4. 指标解释

| 指标 | 字段 | 含义 |
|---|---|---|
| LLM Faithfulness（LLM 忠实性） | `llm_faithfulness` | 生成答案中的事实声明有多少被 context 支持 |
| LLM Answer Relevance（LLM 答案相关性） | `llm_answer_relevance` | 答案是否直接回答问题，并覆盖标准答案要点 |
| Unsupported Claims（无依据声明数） | `unsupported_claim_count` | Judge 判断没有被 context 支持的声明数量 |
| Missing Answer Points（缺失答案要点数） | `missing_answer_point_count` | Judge 判断答案缺少的标准要点数量 |
| Strict Pass（严格通过） | `strict_pass` | `answer_point_coverage >= 0.8` 且 `llm_faithfulness >= 0.8` 且 `llm_answer_relevance >= 0.8` |

也就是说，严格通过不是只看答案像不像标准答案，而是同时要求：

```text
要点覆盖足够
+ 答案有上下文支持
+ 答案确实回答问题
```

## 5. 本次真实结果

| strategy | Strict Pass Rate | Avg Answer Point Coverage | Avg Proxy Faithfulness | Avg LLM Faithfulness | Avg Proxy Answer Relevance | Avg LLM Answer Relevance |
|---|---:|---:|---:|---:|---:|---:|
| `bm25` | 0.35 | 0.6283 | 0.8018 | 0.8075 | 0.6399 | 0.8100 |
| `router` | 0.35 | 0.7033 | 0.8299 | 0.8633 | 0.6399 | 0.8350 |
| `vector` | 0.50 | 0.6975 | 0.8252 | 0.9425 | 0.6935 | 0.8267 |

### 和阶段 7.4 的差异

阶段 7.4 只看答案要点覆盖时：

| strategy | Pass Rate |
|---|---:|
| `bm25` | 0.45 |
| `router` | 0.60 |
| `vector` | 0.55 |

阶段 7.5 加上 LLM Judge 后：

| strategy | Strict Pass Rate |
|---|---:|
| `bm25` | 0.35 |
| `router` | 0.35 |
| `vector` | 0.50 |

这个变化非常重要。

它说明：`router` 在答案要点覆盖上更强，但严格判断 faithfulness（忠实性）后，`vector` 反而更稳。原因是 `vector` 的答案更少出现无依据扩展，平均 `llm_faithfulness=0.9425`，高于 `router=0.8633` 和 `bm25=0.8075`。

## 6. 人话结论

1. Proxy 指标和 LLM Judge 指标不能混为一谈。

   Proxy 指标便宜、快、可复现，但它主要看关键词。LLM Judge 更接近人工判断，会检查声明是否真的由 context 支持。

2. `answer_point_coverage` 高，不代表答案忠实。

   一个答案可能覆盖了标准要点，但同时加入一些 context 不支持的扩展信息。这种答案在 7.4 里可能高分，在 7.5 里会被扣分。

3. `vector` 在严格评测下表现更好。

   本次 `vector` 的 strict pass rate 是 0.50，高于 `bm25` 和 `router` 的 0.35。说明向量检索给 LLM 的上下文更容易支撑最终答案。

4. `router` 仍然有价值。

   `router` 的 answer point coverage 最高，说明它更容易召回“答题所需的信息”。但后续需要更好的 context 控制、rerank 或答案约束，减少无依据扩展。

5. 全局总结题仍然困难。

   `EVAL-0015` 三条路线都没有严格通过。它要求跨文档覆盖监管、传感器、控制系统、事故原因和维护动作，当前 Top-5 context 和短答案生成都不够稳。

## 7. 代表性案例

### EVAL-0002：答案太短

问题：

```text
Which pipeline does BluePump-X100 move cooling water through?
```

`bm25` 和 `router` 生成：

```text
Pipeline-7A
```

这个答案虽然包含关键词，但太短。严格评测认为它没有完整表达 “BluePump-X100 moves cooling water through Pipeline-7A” 这个关系，所以 strict pass 失败。

### EVAL-0015：全局总结失败

问题：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

失败原因：

- 信息分散在多个 chunk
- 答案容易漏掉 `Sensor P-210`
- 答案容易漏掉 `Filter-F33 replacement`
- 有些生成内容有上下文支持，但没有覆盖标准总结链路

这类题后续要靠：

- 更大的 candidate_top_k
- rerank
- global summary 专用 prompt
- Query Router 对总结题选择更强 hybrid 策略

### EVAL-0020：多模态多跳题

问题：

```text
According to the table and diagram, what was Pipeline-7A's pressure status and where was ReliefValve-RV9 installed?
```

`bm25` 生成：

```text
Pipeline-7A's pressure status was below the 9.5 MPa alarm threshold. ReliefValve-RV9 was installed on the discharge side of BluePump-X100.
```

它通过严格评测，说明当前多模态模拟数据里，BM25 对表格字段和图像 caption/OCR 的精确匹配很有效。

## 8. 局限

1. Judge 仍然是本地小模型。

   本次使用 `qwen2.5:3b` 作为评审模型。它能完成基础判断，但会有误判和不稳定输出。正式论文级评测通常会用更强模型或人工抽检。

2. 仍有 1 条 parse failure。

   `EVAL-0015/bm25` 的 Judge 输出过长导致 JSON 截断。该样本本身不是通过样本，但会轻微影响 `bm25` 平均分。报告中保留这个信息，不隐藏实验噪声。

3. LLM Judge 不是 RAGAS 本体。

   当前实现的是接近 RAGAS 思路的本地简化版。后续如果有可用 API 或更强本地模型，可以替换 Judge。

4. Judge 和规则评分可能冲突。

   例如某些答案在 `answer_point_coverage` 上低，但 Judge 认为相关性还可以；也有些答案覆盖要点，但 Judge 认为存在 unsupported claims。这是正常现象，说明不同指标观察的是不同失败面。

## 9. 本阶段产出的能力

现在评测系统已经从 retrieval 走到了 generation 和 judge：

```text
Retrieval Evaluation:
  Hit@K / Recall@K / MRR / Context Precision / Context Recall

Answer Evaluation:
  Answer Point Coverage / Gold Token F1 / Proxy Faithfulness / Proxy Answer Relevance

LLM Judge Evaluation:
  LLM Faithfulness / LLM Answer Relevance / Unsupported Claims / Strict Pass
```

这已经是一个比较完整的 RAG 实验评测闭环。

## 10. 下一阶段

下一阶段建议进入：

- 阶段 7.6：合并 retrieval、answer、LLM judge 三类结果，形成正式实验总表

目标是得到一张可以放进 README 和简历项目里的实验结果表。

