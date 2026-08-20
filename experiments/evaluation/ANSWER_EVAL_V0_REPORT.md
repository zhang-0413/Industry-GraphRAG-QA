# 阶段 7.4：Answer Evaluation 指标脚本报告

## 1. 本阶段目标

阶段 7.3 只回答了一个问题：

> 检索阶段有没有把标准证据 chunk 找回来？

阶段 7.4 继续往后走一步：

> 模型拿到 Top-K context 后，最终生成的答案是否覆盖了标准答案要点？

这一步很重要，因为 RAG 系统不是“检索到证据”就结束。真实问答链路是：

```text
question
  -> retrieval
  -> context
  -> LLM generation
  -> answer
  -> answer evaluation
```

所以 Answer Evaluation（答案生成评测）要评估的是最终答案，而不是只看召回。

## 2. 脚本与运行方式

### 脚本

- `experiments/evaluation/scripts/run_answer_eval_v0.py`

### 输入

- 评测集：`experiments/evaluation/datasets/eval_v0_20.jsonl`
- 检索语料：
  - `experiments/baseline_industry_mini/storage_structure_aware`
  - `experiments/baseline_industry_mini/storage_multimodal`

### 本次运行配置

| 配置 | 值 |
|---|---|
| LLM | `qwen2.5:3b` |
| Ollama host | `http://localhost:11434` |
| top_k | `5` |
| strategies | `bm25`, `vector`, `router` |
| samples | `20` |
| total answers | `60` |
| temperature | `0` |
| num_predict | `120` |

### 运行命令

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\run_answer_eval_v0.py
```

运行前需要确保 Ollama 服务已启动：

```powershell
ollama serve
```

## 3. 输出文件

- 明细 JSONL：`experiments/evaluation/results/answer_eval_v0/answer_eval_v0_records.jsonl`
- 明细 CSV：`experiments/evaluation/results/answer_eval_v0/answer_eval_v0_records.csv`
- 汇总 CSV：`experiments/evaluation/results/answer_eval_v0/answer_eval_v0_summary.csv`

## 4. 本阶段实现的指标

| 指标 | 字段 | 人话解释 |
|---|---|---|
| Pass Rate（通过率） | `pass_rate` | 有多少问题的答案覆盖率达到 0.8 以上 |
| Answer Point Coverage（答案要点覆盖率） | `answer_point_coverage` | 标准答案要点中，有多少被生成答案覆盖 |
| Gold Token F1（标准答案词重合 F1） | `gold_token_f1` | 生成答案和 gold_answer（标准答案）的关键词重合程度 |
| Faithfulness Proxy（忠实性代理指标） | `faithfulness_proxy` | 答案中的关键信息有多少能在 context 中找到 |
| Answer Relevance Proxy（答案相关性代理指标） | `answer_relevance_proxy` | 答案是否覆盖了问题中的关键对象 |
| Generation Latency（生成延迟） | `generation_latency_ms` | LLM 生成答案耗时 |
| Total Latency（总延迟） | `total_latency_ms` | 检索耗时 + 生成耗时 |

注意：`faithfulness_proxy` 和 `answer_relevance_proxy` 是本地规则版 proxy（代理指标），不是最终 RAGAS 指标。后续阶段会继续引入更严格的 Faithfulness（忠实性）和 Answer Relevance（答案相关性）评测。

## 5. 本次真实结果

| strategy | Pass Rate | Avg Answer Point Coverage | Gold Token F1 | Faithfulness Proxy | Answer Relevance Proxy |
|---|---:|---:|---:|---:|---:|
| `bm25` | 0.45 | 0.6283 | 0.6090 | 0.8018 | 0.6399 |
| `vector` | 0.55 | 0.6975 | 0.6290 | 0.8252 | 0.6935 |
| `router` | 0.60 | 0.7033 | 0.6503 | 0.8299 | 0.6399 |

### 人话结论

1. `router` 综合最好。

   它的 Pass Rate（通过率）最高，Answer Point Coverage（答案要点覆盖率）也最高。说明 Query Router（查询路由器）不只是提升检索策略选择，也能间接提升最终答案质量。

2. `vector` 很接近 `router`。

   `vector` 的答案相关性代理指标最高，说明向量检索能提供较丰富的语义上下文。但它也可能引入更多噪声，导致答案不一定稳定覆盖全部要点。

3. `bm25` 最快，但答案覆盖偏低。

   BM25 对编号、数值、设备名很强，但对于跨段落、全局总结、因果解释题，模型拿到的 context 可能不够完整，所以最终答案容易只覆盖部分要点。

4. 检索好不等于答案一定好。

   阶段 7.3 中 `bm25` 和 `vector` 的 Recall@5 都很高，但阶段 7.4 的答案通过率明显低很多。这说明 LLM 生成阶段会带来新的失败类型：漏要点、只回答短语、上下文利用不足、答案截断。

## 6. 代表性样本

### 正确样本：EVAL-0006

问题：

```text
What does Sensor T-200 monitor?
```

生成答案：

```text
Sensor T-200 monitors BluePump-X100 outlet temperature.
```

该样本在 `bm25`、`vector`、`router` 三条路线下都通过，`answer_point_coverage=1.0`。它说明事实型实体关系问题比较适合当前系统。

### 失败样本：EVAL-0015

问题：

```text
Summarize the safety chain involving BluePump-X100 across the manuals and incident report.
```

这个题是 `global_summary`（全局总结）题，标准答案需要覆盖：

- `BluePump-X100` 和 `ReliefValve-RV9`
- `Safety-Regulation-42`
- `Sensor T-200`
- `Sensor P-210`
- `ControlSystem-CS1`
- `Filter-F33`
- `IR-2024-017`
- maintenance action（维护动作）

三条路线都没有通过。原因不是完全没召回，而是生成答案没有完整覆盖所有标准要点。这类问题后续需要：

- 更大的候选池
- rerank（重排序）
- summary-aware chunk（总结友好切片）
- Query Router 对 global_summary 题使用更强的 hybrid 策略

### 多模态样本：EVAL-0020

问题：

```text
According to the table and diagram, what was Pipeline-7A's pressure status and where was ReliefValve-RV9 installed?
```

`bm25` 和 `router` 都通过，`vector` 没有通过。

这说明多模态题不能只靠语义相似度。表格和图片题更需要：

- `content_type=table`
- `content_type=image`
- caption（图注）
- OCR 文本
- metadata filter（元数据过滤）

## 7. 当前脚本的局限

1. Answer Point Coverage 是规则评分，不是人工评分。

   它通过实体、数字、关键词和轻量词干匹配判断答案是否覆盖标准要点。优点是可解释、免费、可复现；缺点是对复杂语义仍然不如人工或 LLM judge。

2. Faithfulness Proxy 不是最终忠实性评测。

   当前只检查答案关键词是否能在 context 中找到。真正的 Faithfulness（忠实性）要判断每个声明是否由 context 支持，这需要更细粒度的 claim decomposition（声明拆分）或 RAGAS。

3. Answer Relevance Proxy 也只是粗粒度指标。

   它主要看答案是否覆盖问题关键词，不能完全判断答案是否真正回答了问题。

4. `num_predict=120` 可能导致长答案截断。

   对 global_summary（全局总结）题，模型可能还没写完就停止。正式实验可以提高 `num_predict`，但会增加 latency（延迟）。

## 8. 本阶段得到的关键认识

阶段 7.3 的 retrieval evaluation（检索评测）回答：

> 证据有没有找回来？

阶段 7.4 的 answer evaluation（答案评测）回答：

> 找回来之后，模型有没有把答案写对？

两者不能互相替代。

在简历项目里，这一点很重要。因为它能说明你不是只会搭 RAG demo，而是知道 RAG 的失败可能发生在不同环节：

- 文档解析失败
- chunk 切片失败
- 检索召回失败
- rerank 排序失败
- context 拼接失败
- LLM 生成失败
- 评测指标过松或过严

## 9. 下一阶段

下一阶段建议进入：

- 阶段 7.5：实现更严格的 Faithfulness（忠实性）和 Answer Relevance（答案相关性）评测

目标是把当前 proxy 指标升级为更接近 RAGAS 的评测方式。

