# Source Code Guide

本文档说明阅读 LightRAG 源码时应该从哪些文件开始，以及这些文件在 RAG 流程中的位置。

## 1. 核心文件

| 文件 | 作用 | 应重点看什么 |
| --- | --- | --- |
| `lightrag/base.py` | 数据结构和接口定义 | `QueryParam`、文档状态、存储接口 |
| `lightrag/lightrag.py` | LightRAG 主类 | `insert()`、`ainsert()`、`query()`、`aquery()` |
| `lightrag/operate.py` | 核心操作流程 | `naive_query`、`kg_query`、上下文构建、实体关系抽取 |
| `lightrag/kg/` | 存储实现 | 向量存储、KV 存储、图存储 |
| `prompts/` | Prompt 模板 | 实体关系抽取 prompt、回答 prompt |

## 2. 查询调用链

用户调用：

```python
rag.query("question", param=QueryParam(mode="mix"))
```

大致链路：

```text
rag.query()
-> rag.aquery()
-> read QueryParam.mode
-> naive_query / kg_query / mix_kg_vector_query
-> build query context
-> call LLM
-> return answer
```

不同模式：

| mode | 查询思路 |
| --- | --- |
| `naive` | 直接查询 `chunks_vdb`，最像普通 Vector RAG |
| `local` | 先查实体 `entities_vdb`，再扩展关系和原文 chunk |
| `global` | 先查关系 `relationships_vdb`，再扩展实体和原文 chunk |
| `hybrid` | 同时使用实体和关系线索 |
| `mix` | GraphRAG 和 Vector RAG 混合 |

## 3. 入库调用链

用户调用：

```python
rag.insert(text)
```

大致链路：

```text
insert()
-> ainsert()
-> 文档去重
-> chunking
-> write full_docs
-> write text_chunks
-> upsert chunks_vdb
-> extract entities and relationships
-> merge nodes and edges
-> write entities_vdb / relationships_vdb
-> write graph store
-> update doc_status
```

## 4. 关键存储关系

| 存储 | 保存什么 | 服务哪个阶段 |
| --- | --- | --- |
| `full_docs` | 完整原文 | 追溯整篇文档 |
| `text_chunks` | chunk 原文和 metadata | 检索后拼上下文 |
| `chunks_vdb` | chunk embedding | naive / vector 检索 |
| `entities_vdb` | 实体描述向量 | local 检索 |
| `relationships_vdb` | 关系描述向量 | global 检索 |
| `graph store` | 实体节点和关系边 | 图谱扩展和关系查询 |

## 5. 二次开发建议接入点

| 目标 | 推荐接入位置 |
| --- | --- |
| 结构感知切片 | 入库阶段 chunking 之前或替换 chunking 函数 |
| BM25 检索 | 查询阶段，和 `chunks_vdb` 检索并行召回 |
| RRF 融合 | BM25 / Vector / Graph 候选返回之后 |
| Rerank | 候选池召回之后，最终 Top-K 之前 |
| Query Router | `aquery()` 分流前，或业务封装层 |
| Metadata Filter | 候选召回之后、融合或 rerank 之前 |
| 增量索引 | 入库阶段 chunk 生成后、embedding 前 |

## 6. 阅读建议

建议阅读顺序：

```text
base.py QueryParam
-> lightrag.py query / aquery
-> operate.py naive_query
-> operate.py kg_query
-> build query context
-> lightrag.py insert / ainsert
-> chunk embedding
-> entity / relation extraction
-> graph and vector store upsert
```
