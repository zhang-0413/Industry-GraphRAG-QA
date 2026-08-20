# Incremental Index Design

本文档说明本项目的增量索引设计。

## 1. 为什么需要增量索引

如果文档发生变化后每次都整库重新 embedding，会带来三个问题：

- 成本高：所有 chunk 都要重新向量化。
- 时间慢：大型知识库更新会很久。
- 风险大：更新过程中断可能导致索引状态不一致。

增量索引的目标是：

```text
只处理发生变化的 chunk。
```

## 2. 核心字段

| 字段 | 含义 | 作用 |
| --- | --- | --- |
| `document_id` | 文档唯一 ID | 判断是哪一篇文档 |
| `chunk_id` | chunk 唯一 ID | 判断是哪一个切片 |
| `content_hash` | chunk 内容哈希 | 判断内容是否发生变化 |
| `version` | 文档版本 | 记录更新历史 |

## 3. content_hash 是什么

`content_hash` 是对 chunk 内容计算出的摘要。

如果两个 chunk 内容完全一样，它们的 hash 应该一样。

如果内容有任何变化，hash 通常会变化。

因此它适合用来判断：

```text
这个 chunk 是否需要重新 embedding？
```

## 4. 更新策略

| 情况 | 判断方式 | 操作 |
| --- | --- | --- |
| chunk 没变 | `chunk_id` 存在且 `content_hash` 相同 | 跳过 |
| 新增 chunk | 新版本有，旧版本没有 | 新增 embedding 和索引 |
| 修改 chunk | `chunk_id` 相同但 `content_hash` 不同 | 重新 embedding 并 upsert |
| 删除 chunk | 旧版本有，新版本没有 | 删除 text、vector、graph 中的对应数据 |

## 5. 为什么 chunk_id 要稳定

如果文档只改了一小段，但所有 chunk_id 都变化，系统会误以为所有 chunk 都是新 chunk。

后果：

```text
无法复用旧 embedding
-> 增量索引退化成全量重建
```

所以结构感知切片要尽量让 chunk_id 稳定，例如基于：

```text
document_id + chapter + section + local_index
```

而不是完全依赖全局顺序。

## 6. 为什么要删除旧索引

如果删除或修改了原文，但向量库和图谱中旧数据还在，查询时可能召回过时证据。

这会导致：

- stale chunks
- 答案引用旧信息
- vector store 和 graph store 不一致
- 最终答案与新文档矛盾

## 7. 实验结果

| Method | Embedding Count | Saved Ratio | Stale Chunks |
| --- | ---: | ---: | ---: |
| full_reindex | 34 | 0 | 0 |
| incremental_with_graph_cleanup | 2 | 94.12% | 0 |
| incremental_without_delete | 2 | 94.12% | 1 |
| incremental_without_hash | 1 | 97.06% | 3 |

结论：

```text
content_hash 检测修改，delete cleanup 清理旧数据，二者都不能省。
```

## 8. 接入 LightRAG 的位置

推荐接入位置：

```text
document parsing
-> structure-aware chunking
-> compute chunk_id and content_hash
-> compare old and new chunk index
-> only embed new or changed chunks
-> delete removed chunks
-> update vector store and graph store
```

也就是说，增量判断应该发生在 embedding 之前，而不是等所有向量都生成之后。
