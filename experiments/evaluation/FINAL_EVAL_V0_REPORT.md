# 阶段 7.6：正式实验总表报告

## 1. 本阶段目标

阶段 7.6 的目标是把前面三类评测合并成一张正式实验总表：

```text
7.3 Retrieval Evaluation
  -> Hit@K / Recall@K / MRR / Context Precision / Context Recall

7.4 Answer Evaluation
  -> Answer Point Coverage / Answer Pass Rate / Gold Token F1

7.5 LLM Judge Evaluation
  -> LLM Faithfulness / LLM Answer Relevance / Strict Pass Rate
```

最终得到一张可以放进 README、实验报告和简历项目材料的表。

## 2. 新增脚本

- `experiments/evaluation/scripts/merge_eval_results_v0.py`

该脚本读取：

- `experiments/evaluation/results/retrieval_eval_v0/retrieval_eval_v0_summary.csv`
- `experiments/evaluation/results/answer_eval_v0/answer_eval_v0_summary.csv`
- `experiments/evaluation/results/llm_judge_eval_v0/llm_judge_eval_v0_summary.csv`

然后合并 `top_k=5` 且三类结果都存在的策略。

## 3. 输出文件

- `experiments/evaluation/results/final_eval_v0/final_eval_v0_summary.csv`
- `experiments/evaluation/results/final_eval_v0/final_eval_v0_summary.md`

运行命令：

```powershell
cd "C:\Users\79310\Desktop\项目\LightRAG"
.\.venv\Scripts\python.exe experiments\evaluation\scripts\merge_eval_results_v0.py
```

## 4. README 版实验总表

| strategy | retrieval_recall_at_5 | answer_point_coverage | answer_pass_rate | llm_faithfulness | llm_answer_relevance | strict_pass_rate | retrieval_latency_ms | total_answer_latency_ms | recommendation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `vector` | 0.9625 | 0.6975 | 0.5500 | 0.9425 | 0.8267 | 0.5000 | 808.28 | 3321.66 | Current best strict baseline |
| `router` | 0.9125 | 0.7033 | 0.6000 | 0.8633 | 0.8350 | 0.3500 | 509.13 | 3134.84 | Best candidate for engineering optimization |
| `bm25` | 0.9375 | 0.6283 | 0.4500 | 0.8075 | 0.8100 | 0.3500 | 0.82 | 2597.18 | Keep as exact-match branch in hybrid/router |

## 5. 指标怎么读

### `retrieval_recall_at_5`

Top-5 检索结果中覆盖了多少标准证据。

它回答的是：

> 证据有没有被找回来？

### `answer_point_coverage`

生成答案覆盖了多少标准答案要点。

它回答的是：

> 模型有没有把该说的事实说出来？

### `answer_pass_rate`

规则版答案评测中，通过的样本比例。

当前通过条件主要依赖 `answer_point_coverage >= 0.8`。

### `llm_faithfulness`

LLM Judge 判断答案事实声明有多少被 context 支持。

它回答的是：

> 答案有没有编，或者有没有无依据扩展？

### `llm_answer_relevance`

LLM Judge 判断答案是否直接回答问题，并覆盖标准要点。

它回答的是：

> 答案是不是问什么答什么？

### `strict_pass_rate`

最严格的综合通过率。

当前定义：

```text
answer_point_coverage >= 0.8
and llm_faithfulness >= 0.8
and llm_answer_relevance >= 0.8
```

它回答的是：

> 这个答案是否同时完整、忠实、相关？

## 6. 本次实验结论

### 结论 1：`vector` 是当前最好的 strict baseline

`vector` 的 strict pass rate 是 `0.5000`，高于 `router` 和 `bm25`。

原因是它的 `llm_faithfulness=0.9425`，说明生成答案里的事实声明更容易被上下文支持。

### 结论 2：`router` 是最值得继续优化的工程方案

`router` 的 `answer_point_coverage=0.7033` 和 `answer_pass_rate=0.6000` 是最高的。

这说明 Query Router（查询路由器）更容易找齐答题所需信息。但它的 strict pass rate 没有最高，说明还需要控制 context 噪声和无依据扩展。

后续优化方向：

- router 对表格题启用 table filter
- router 对图片题启用 image filter
- router 对总结题启用 hybrid + rerank
- generation prompt 要求逐条覆盖证据

### 结论 3：`bm25` 应保留为精确匹配分支

`bm25` 的 retrieval latency 只有 `0.82 ms`，远快于 `vector` 和 `router`。

而且它对编号、数值、表格字段、OCR/caption 关键词非常强。

所以它不应该被放弃，而应该作为 hybrid retrieval 和 router 的一个分支。

### 结论 4：不能只看单一指标

如果只看 `retrieval_recall_at_5`，会觉得 `vector` 和 `bm25` 都很强。

如果只看 `answer_pass_rate`，会觉得 `router` 最强。

如果看 `strict_pass_rate`，当前 `vector` 最强。

这说明 RAG 评测必须拆成多个层次：

```text
检索是否找回证据
答案是否覆盖要点
答案是否忠实于上下文
答案是否直接回答问题
系统是否足够快
```

## 7. 可以写进 README 的版本

```markdown
### Evaluation Results

We evaluated retrieval quality, answer quality, and LLM-judge faithfulness on a 20-question industry-document benchmark.

| Method | Recall@5 | Answer Coverage | Answer Pass | Faithfulness | Relevance | Strict Pass |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.9625 | 0.6975 | 0.5500 | 0.9425 | 0.8267 | 0.5000 |
| Router | 0.9125 | 0.7033 | 0.6000 | 0.8633 | 0.8350 | 0.3500 |
| BM25 | 0.9375 | 0.6283 | 0.4500 | 0.8075 | 0.8100 | 0.3500 |

Vector retrieval achieved the best strict-pass score, while the query router achieved the best answer-point coverage and remains the most promising direction for engineering optimization.
```

## 8. 当前局限

1. 数据集仍然较小。

   当前是 `eval_v0_20`，只有 20 条问题。后续正式版本要扩展到 100-300 条。

2. Judge 模型是本地小模型。

   当前使用 `qwen2.5:3b`，能做基础评测，但不是最终人工审阅。

3. `bm25` 有 1 条 Judge parse failure。

   `EVAL-0015/bm25` 的 Judge 输出过长导致 JSON 截断。该样本本身不是通过样本，但会轻微影响平均值。

4. 当前只合并了 `bm25`、`vector`、`router`。

   因为 7.4 和 7.5 的 answer/judge 评测只跑了这三种策略。后续要扩展到：

   - graph
   - mix
   - BM25 + Vector
   - BM25 + Vector + Graph
   - Hybrid + Rerank

## 9. 下一阶段

阶段 7 已经完成了从数据集到评测闭环的主线：

```text
评测集 schema
-> eval_v0_20
-> retrieval metrics
-> answer metrics
-> LLM judge metrics
-> final evaluation table
```

下一步建议进入：

- 阶段 7.7：阶段 7 总复盘与评测体系面试题

之后再进入：

- 阶段 8：实验和消融实验

