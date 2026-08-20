# Interview Q&A

本文档整理本项目相关面试题和参考回答。

## 1. GraphRAG 和普通 Vector RAG 有什么区别？

普通 Vector RAG 主要依赖 chunk embedding 做语义相似度检索。

GraphRAG 除了 chunk，还会抽取实体和关系，构建知识图谱。查询时可以利用实体、关系和图结构来组织上下文。

简短回答：

```text
Vector RAG 查相似文本，GraphRAG 还查实体关系结构。
```

## 2. 为什么不能说 GraphRAG 一定优于 Vector RAG？

因为不同问题适合不同检索方式。

Graph 对实体关系、多跳和全局关联问题有帮助，但对编号、数值、表格字段这类精确问题，不一定比 BM25 或 Vector 更好。

本项目实验中，Graph 单路 Recall@5 低于 BM25 和 Vector，因此最终采用条件启用。

## 3. 为什么需要 chunk？

LLM 和 embedding model 不能高效处理整篇大文档。chunk 可以把文档拆成较小、可索引、可检索、可拼接上下文的单元。

如果不 chunk：

- 上下文太长
- 检索粒度太粗
- 噪声太多
- 成本高

## 4. 固定长度切片有什么问题？

固定长度切片只按 token 或字符数量切分，可能把一个完整章节、段落、表格或语义关系切断。

复杂行业文档更适合结构感知切片，因为标题、页码、章节和表格结构都是重要语义信息。

## 5. BM25 和向量检索有什么区别？

BM25 是基于关键词匹配，适合编号、术语、精确字段和数值。

向量检索是基于语义相似度，适合同义表达、语义解释和概念相近的问题。

工程上通常把二者结合。

## 6. RRF 是什么？

RRF 是 Reciprocal Rank Fusion，倒数排名融合。

它不直接比较不同检索器的原始 score，而是根据每一路结果的 rank 融合排序。

优点是简单、稳定，适合融合 BM25 和 Vector 这类分数尺度不同的检索器。

## 7. Rerank 为什么放在召回之后？

因为 rerank 只能重排已经召回的候选，不能找回候选池外的证据。

正确顺序是：

```text
BM25 / Vector / Graph recall
-> candidate pool
-> rerank
-> final Top-K
```

## 8. Rerank 什么时候可能伤害结果？

如果 reranker 和任务不匹配，它可能把正确证据排到后面，把看起来相关但不能回答问题的 chunk 排到前面。

本项目实验说明，全局开启 rerank 不一定提升，所以最终采用条件启用。

## 9. Query Router 的作用是什么？

Query Router 根据问题类型选择检索策略。

例如：

- 编号/数值：BM25
- 语义解释：Vector
- 表格：Metadata Filter + BM25
- 图片：Metadata Filter + image description
- 实体关系：BM25 + Vector，必要时 Graph
- 全局总结：扩大候选池，必要时 rerank

## 10. 为什么要用 document_id、chunk_id、content_hash、version？

这些字段用于增量索引：

- `document_id` 定位文档
- `chunk_id` 定位切片
- `content_hash` 判断内容是否变化
- `version` 记录版本

这样文档更新时，只需要处理新增、修改和删除的 chunk，不用整库重新 embedding。

## 11. content_hash 解决什么问题？

它用来判断 chunk 内容是否发生变化。

如果 `chunk_id` 相同但 `content_hash` 不同，说明这个 chunk 被修改了，需要重新 embedding 并更新索引。

## 12. 不删除旧 chunk 会怎样？

会产生 stale chunks，也就是过时切片。

查询时可能召回旧信息，导致答案和新文档矛盾。

## 13. 为什么 Metadata Filter 对多模态重要？

因为表格题和图片题需要先缩小候选范围。

如果问题问表格数值，却把普通文本、图片描述和关系 chunk 都混进候选池，Context Precision 会下降。

Metadata Filter 可以按 `content_type=table` 或 `content_type=image` 过滤候选，减少噪声。

## 14. Recall@K 高，为什么答案仍然可能错？

因为证据被召回不代表 LLM 一定正确使用它。

可能出现：

- 正确证据排得太靠后
- 上下文噪声太多
- LLM 忽略关键证据
- LLM 产生 unsupported claims

所以还要评估 Answer Coverage、Faithfulness 和 Answer Relevance。

## 15. 你的工作和原版 LightRAG 的区别是什么？

可以这样回答：

```text
原版 LightRAG 提供了 GraphRAG 的基础能力，包括文档入库、chunk embedding、实体关系抽取、图谱构建和多种查询模式。

我的工作是在理解和复现原版流程的基础上，围绕复杂行业文档做了二次开发实验：结构感知切片、BM25 + Vector + RRF、Query Router、条件 Rerank、Metadata Filter、增量索引和评测体系。

最终结论不是所有模块全开，而是 BM25 + Vector + RRF 作为默认主干，Graph / Rerank / Metadata Filter 按问题类型条件启用。
```

## 16. 简历里怎么描述这个项目？

参考：

```text
基于 HKUDS/LightRAG 二次开发复杂行业文档知识库问答系统，系统梳理并复现 GraphRAG 从文档入库、chunk embedding、实体关系抽取、图谱构建到多模式查询的完整链路。在原始 Vector / Graph 检索基础上，设计结构感知切片、BM25 + Vector + RRF 混合检索、规则版 Query Router、条件 Rerank、Metadata Filter 和增量索引机制，并构建覆盖事实、数值、实体关系、跨文档、表格和图片问题的小型评测集。实验结果显示，BM25 + Vector + RRF 相比 BM25 将 Recall@5 从 0.9375 提升到 0.9625，Query Router 进一步提升到 0.9875；增量索引将 embedding 重算量从 34 次降低到 2 次，节省 94.12%；多模态 Metadata Filter 将表格/图片问题 Context Precision 从 0.25 提升到 1.0。
```
