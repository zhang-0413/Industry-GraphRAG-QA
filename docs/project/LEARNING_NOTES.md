# Learning Notes

本文档总结本项目的学习路线。它不是 LightRAG 官方文档，而是围绕“如何从开源项目学习 RAG，并做出可写入简历的二次开发项目”整理的工程学习笔记。

## 1. 学习目标

项目目标是通过 LightRAG 系统掌握：

- RAG 完整流程
- 文档解析、切片和 metadata
- Embedding 和向量数据库
- BM25、Vector Retrieval、Hybrid Retrieval
- GraphRAG 中的实体、关系和图存储
- Query Router 和 Rerank
- Recall@K、Hit@K、MRR、Context Precision、Faithfulness、Answer Relevance
- 增量索引和文档版本更新
- 多模态 RAG 的表格、图片和 metadata filter

## 2. 已完成阶段

| 阶段 | 主题 | 产出 |
| --- | --- | --- |
| 1 | 项目整体认识 | 理解 LightRAG 解决什么问题，以及 GraphRAG 和 Vector RAG 的区别 |
| 2 | 运行原始项目 | 使用 Ollama 跑通本地最小 Demo |
| 3 | 源码结构理解 | 阅读 `base.py`、`lightrag.py`、`operate.py` 查询链路 |
| 4 | 入库流程理解 | 阅读 `insert`、chunk、embedding、实体关系抽取和 graph 写入流程 |
| 5 | Baseline | 构建 mini dataset 并跑 15×5 baseline 实验 |
| 6 | 二次开发实验 | 结构感知切片、混合检索、rerank、router、多模态设计 |
| 7 | 正式评测集 | 创建 `eval_v0_20.jsonl` 和评测脚本 |
| 8 | 实验与消融 | 形成最终优化方案和实验结论 |
| 9 | README 和 GitHub 整理 | 形成项目首页、文档区和仓库结构规划 |

## 3. 核心认知

### 3.1 LightRAG 不是只做向量检索

普通 Vector RAG 主要流程是：

```text
document -> chunk -> embedding -> vector search -> context -> answer
```

LightRAG 额外引入：

```text
chunk -> entity extraction -> relation extraction -> graph store
```

因此查询时不仅能查相似文本，也能围绕实体和关系组织上下文。

### 3.2 Graph 不是默认越多越好

实验表明，Graph 检索在实体关系问题上有价值，但直接加入所有问题会引入噪声。最终策略不是 Graph 全开，而是由 Query Router 条件启用。

### 3.3 Rerank 不能替代召回

Rerank 只负责重排候选池里的内容，不能找回没有被 BM25、Vector 或 Graph 召回的证据。因此要区分：

```text
candidate_top_k -> 扩大候选池，解决有没有召回
final_top_k -> 控制最终上下文，解决给 LLM 多少证据
rerank -> 改变候选顺序，解决证据排不排得上来
```

### 3.4 评测必须分层

只看答案对错不够。RAG 至少要看：

- 是否召回证据
- 证据是否排在前面
- 上下文是否包含噪声
- 答案是否覆盖关键要点
- 答案是否忠实于上下文

## 4. 当前项目结论

最终推荐链路：

```text
Document
-> Parser / MinerU
-> Structure-aware Chunk
-> document_id / chunk_id / content_hash / version
-> BM25 Index + Vector Store + selective Graph Store
-> Query Router
-> Metadata Filter
-> BM25 + Vector + RRF by default
-> Conditional Graph / Conditional Rerank
-> Final Top-K Context
-> LLM Answer
-> Evaluation
```

最重要的工程结论：

```text
不要堆模块，要通过实验判断模块什么时候有用。
```
