# Experiment Guide

本文档说明如何运行本项目的评测脚本。所有命令默认在仓库根目录执行。

## 1. 环境准备

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -U pip
pip install -e .
```

准备 Ollama 模型：

```powershell
ollama pull qwen2.5:3b
ollama pull nomic-embed-text
ollama list
```

如果 Ollama 服务没有启动：

```powershell
ollama serve
```

## 2. 数据集

正式小型评测集：

```text
experiments/evaluation/datasets/eval_v0_20.jsonl
```

校验数据集：

```powershell
python experiments/evaluation/scripts/validate_dataset.py
python experiments/evaluation/scripts/validate_dataset_evidence.py
```

## 3. 检索评测

```powershell
python experiments/evaluation/scripts/run_retrieval_eval_v0.py
```

输出：

```text
experiments/evaluation/RETRIEVAL_EVAL_V0_REPORT.md
```

关注指标：

- Recall@K
- Hit@K
- MRR
- Context Precision

## 4. 答案评测

```powershell
python experiments/evaluation/scripts/run_answer_eval_v0.py
```

输出：

```text
experiments/evaluation/ANSWER_EVAL_V0_REPORT.md
```

关注指标：

- Answer Coverage
- Answer Pass Rate
- Faithfulness Proxy
- Answer Relevance Proxy

## 5. 单路检索对比

```powershell
python experiments/evaluation/scripts/analyze_single_route_retrieval_v0.py
```

对比：

- BM25
- Vector
- Graph

结论：

```text
BM25 精确，Vector 语义召回强，Graph 不适合作默认全局路线。
```

## 6. 混合检索实验

```powershell
python experiments/evaluation/scripts/run_hybrid_retrieval_v0.py
```

对比：

- BM25
- Vector
- Graph
- BM25 + Vector + RRF
- BM25 + Vector + Graph + RRF

结论：

```text
BM25 + Vector + RRF 是当前最稳的默认组合。
```

## 7. Rerank 消融

```powershell
python experiments/evaluation/scripts/run_rerank_ablation_v0.py
```

验证：

- rerank 是否能把正确证据排到前面
- rerank 是否会伤害简单问题
- graph noise 是否能被 rerank 修复

结论：

```text
Rerank 不能全局开启，只能条件启用。
```

## 8. Query Router 消融

```powershell
python experiments/evaluation/scripts/run_query_router_ablation_v0.py
```

验证：

- 固定检索策略 vs Query Router
- safe router vs aggressive graph/rerank router

结论：

```text
Router 的价值是避免复杂模块过度使用。
```

## 9. Metadata Filter 消融

```powershell
python experiments/evaluation/scripts/run_metadata_filter_ablation_v0.py
```

验证：

- 表格问题是否应该过滤 `content_type=table`
- 图片问题是否应该过滤 `content_type=image`
- metadata filter 是否减少噪声

结论：

```text
Metadata Filter 主要提升 Context Precision，尤其适合表格、图片和多跳问题。
```

## 10. 增量索引消融

```powershell
python experiments/evaluation/scripts/run_incremental_index_ablation_v0.py
```

验证：

- full reindex vs incremental update
- without hash 的错误
- without delete 的错误
- unstable chunk_id 的错误

结论：

```text
document_id + chunk_id + content_hash + version 是增量索引的核心。
```

## 11. 最终实验表

```powershell
python experiments/evaluation/scripts/merge_stage8_final_table_v0.py
```

输出：

```text
experiments/evaluation/STAGE8_FINAL_OPTIMIZED_EXPERIMENT_TABLE_V0.md
```

## 12. 推荐完整运行顺序

```powershell
python experiments/evaluation/scripts/run_retrieval_eval_v0.py
python experiments/evaluation/scripts/run_answer_eval_v0.py
python experiments/evaluation/scripts/analyze_single_route_retrieval_v0.py
python experiments/evaluation/scripts/run_hybrid_retrieval_v0.py
python experiments/evaluation/scripts/run_rerank_ablation_v0.py
python experiments/evaluation/scripts/run_query_router_ablation_v0.py
python experiments/evaluation/scripts/run_metadata_filter_ablation_v0.py
python experiments/evaluation/scripts/run_incremental_index_ablation_v0.py
python experiments/evaluation/scripts/merge_stage8_final_table_v0.py
```
