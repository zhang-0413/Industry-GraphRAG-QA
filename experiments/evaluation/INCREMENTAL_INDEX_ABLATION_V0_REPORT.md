# 阶段 8.8：增量索引消融实验报告

## 1. 本阶段做了什么

本阶段把 8.7 的设计变成了可运行实验。

实验目标：

```text
对比 full_reindex（整库重建）和 incremental_index（增量索引）
看它们在文档更新时需要重算多少 embedding
同时检查是否会留下旧 chunk、旧数值、旧图谱贡献
```

本实验没有修改 LightRAG 原始源码，只在 `experiments/evaluation/scripts` 下实现独立实验脚本。

## 2. 实验输入

基础数据来自真实已有工作目录：

`experiments/baseline_industry_mini/storage_structure_aware/kv_store_text_chunks.json`

初始版本 `v1` 包含 11 个 structure-aware chunks（结构感知切片）。

然后构造 3 次文档变化：

| Transition（版本变化） | 变化内容 | 期望动作 |
| --- | --- | --- |
| `v1_to_v2_threshold_update` | `Pipeline-7A` 告警阈值从 `9.5 MPa` 改成 `9.2 MPa` | 1 个 `modified` chunk |
| `v2_to_v3_add_followup` | 新增 `Follow-up Verification` 章节 | 1 个 `added` chunk |
| `v3_to_v4_delete_control_system` | 删除 `Control System` 章节 | 1 个 `deleted` chunk |

真实 diff 结果：

```text
v1 -> v2: modified 1
v2 -> v3: added 1
v3 -> v4: deleted 1
```

## 3. 对比策略

| Strategy（策略） | 含义 |
| --- | --- |
| `full_reindex` | 每次文档变化后，所有新版本 chunk 全部重新 embedding、重建索引 |
| `incremental_with_graph_cleanup` | 正确增量方案，只处理 added / modified / deleted |
| `incremental_without_delete` | 反例：新增和修改会处理，但删除 chunk 时不清理旧索引 |
| `incremental_without_hash` | 反例：只看 `chunk_id`，不看 `content_hash` |
| `unstable_chunk_id` | 反例：每次更新 chunk_id 都变化，导致增量退化为全量 |

## 4. 指标解释

| 指标 | 中文含义 |
| --- | --- |
| `embedding_recompute_count` | 实际需要重新生成 embedding 的 chunk 数 |
| `embedding_saved_ratio` | 相对整库重建节省的 embedding 比例 |
| `text_upsert_count` | 需要写入/更新 text_chunks 的数量 |
| `delete_count` | 需要删除的 chunk 数 |
| `graph_cleanup_count` | 需要清理旧图谱贡献的 chunk 数 |
| `graph_rebuild_count` | 需要重新抽取实体关系并写图谱的 chunk 数 |
| `stale_chunk_count` | 和目标新版本不一致的残留 chunk 数 |
| `missing_chunk_count` | 新版本中应存在但索引里缺失的 chunk 数 |
| `query_pass_rate` | 更新后验证查询是否通过 |
| `measured_embedding_latency_ms` | 本地 Ollama 实测 embedding 耗时 |

注意：

`embedding_recompute_count` 是最重要的成本指标；`stale_chunk_count` 和 `query_pass_rate` 是最重要的一致性指标。

## 5. 整体结果

| Strategy | Embedding Recompute | Saved Ratio | Stale Chunks | Missing Chunks | Query Pass Rate | Embedding Latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `incremental_with_graph_cleanup` | 2 | 0.9412 | 0 | 0 | 1.0000 | 680.26 ms |
| `full_reindex` | 34 | 0.0000 | 0 | 0 | 1.0000 | 1485.98 ms |
| `unstable_chunk_id` | 34 | 0.0000 | 34 | 34 | 1.0000 | 1321.15 ms |
| `incremental_without_delete` | 2 | 0.9412 | 1 | 0 | 0.6667 | 674.64 ms |
| `incremental_without_hash` | 1 | 0.9706 | 3 | 0 | 0.6667 | 331.05 ms |

## 6. 人话解释

### 6.1 正确增量方案节省了 94.12% embedding

三次更新后，整库重建一共需要 embedding：

```text
v2: 11
v3: 12
v4: 11
total = 34
```

正确增量方案只需要 embedding：

```text
v1 -> v2: modified 1
v2 -> v3: added 1
v3 -> v4: deleted 1，不需要 embedding
total = 2
```

所以节省比例是：

```text
1 - 2 / 34 = 94.12%
```

这就是增量索引可以写进简历的核心工程价值：

```text
文档更新成本从 O(total_chunks) 降低到 O(changed_chunks)
```

### 6.2 full_reindex 正确但浪费

`full_reindex` 的 `query_pass_rate` 是 1.0，说明整库重建不会留下旧数据。

但它每次都重新处理所有 chunk，三次更新重算 34 个 embedding。

在真实项目里，如果是 10 万个 chunk，哪怕只改了 2 个 chunk，整库重建也要重算 10 万个 embedding，这就是成本浪费。

### 6.3 incremental_with_graph_cleanup 是目标方案

`incremental_with_graph_cleanup` 达到了：

```text
embedding_recompute_count = 2
stale_chunk_count = 0
missing_chunk_count = 0
query_pass_rate = 1.0
```

这说明它既省成本，又没有留下旧数据。

它的动作逻辑是：

| Action | 处理方式 |
| --- | --- |
| `unchanged` | 不动 |
| `added` | 写入 text_chunks，生成 embedding，抽取实体关系，写入图谱 |
| `modified` | 删除旧贡献，再写入新内容、新 embedding、新实体关系 |
| `deleted` | 删除 text_chunks、chunks_vdb，并清理 graph/entity/relation 贡献 |

### 6.4 incremental_without_hash 为什么失败

`incremental_without_hash` 的 `embedding_saved_ratio` 看起来最高：0.9706。

但这是假的优秀。

它只看 `chunk_id`，不看 `content_hash`，所以 `v1 -> v2` 的阈值修改没有被发现。

失败查询：

```text
What is the alarm threshold for Pipeline-7A?
```

检索结果仍然包含旧内容：

```text
The alarm threshold for Pipeline-7A is 9.5 MPa.
Sensor P-210 must trigger a high-pressure alarm when Pipeline-7A pressure reaches 9.5 MPa.
```

这说明：

```text
不看 content_hash 会让修改过的 chunk 变成 stale chunk（陈旧切片）
```

### 6.5 incremental_without_delete 为什么失败

`incremental_without_delete` 能处理新增和修改，但不处理删除。

在 `v3 -> v4` 中，我们删除了 `Control System` 章节。

失败查询：

```text
What does ControlSystem-CS1 start when either sensor reports an abnormal event?
```

它仍然检索到了已删除 chunk：

```text
ControlSystem-CS1 starts an inspection workflow when either sensor reports an abnormal event.
```

这说明：

```text
删除 chunk 时，如果只更新新增/修改，不清理旧索引，用户仍然会查到已经不存在的知识。
```

### 6.6 unstable_chunk_id 为什么会退化成整库重建

`unstable_chunk_id` 的 `embedding_recompute_count` 是 34，和整库重建一样。

原因是：

```text
每次更新后 chunk_id 都变了
系统无法判断哪些 chunk 其实没变
于是只能把所有旧 chunk 当 deleted
把所有新 chunk 当 added
```

这说明结构感知切片不仅是为了检索质量，也服务于增量索引。

稳定 chunk_id 的前提是 chunk 边界尽量稳定：

```text
document_id + chapter + section + local_order + content_hash
```

如果切片边界一变，后续 chunk 全部漂移，增量索引就失效。

## 7. 分版本结果

| Transition | Strategy | Recompute | Saved Ratio | Stale |
| --- | --- | ---: | ---: | ---: |
| v1 -> v2 | full_reindex | 11 | 0.0000 | 0 |
| v1 -> v2 | incremental_with_graph_cleanup | 1 | 0.9091 | 0 |
| v1 -> v2 | incremental_without_hash | 0 | 1.0000 | 1 |
| v2 -> v3 | full_reindex | 12 | 0.0000 | 0 |
| v2 -> v3 | incremental_with_graph_cleanup | 1 | 0.9167 | 0 |
| v3 -> v4 | full_reindex | 11 | 0.0000 | 0 |
| v3 -> v4 | incremental_with_graph_cleanup | 0 | 1.0000 | 0 |
| v3 -> v4 | incremental_without_delete | 0 | 1.0000 | 1 |

## 8. 和 LightRAG 源码的关系

LightRAG 原版已有几个可复用基础：

### 8.1 `DocProcessingStatus`（文档处理状态）

位置：

`lightrag/base.py`

已有字段：

```text
chunks_count
chunks_list
metadata
content_hash
```

其中：

`chunks_list` 可以用来追踪文档拥有的 chunk。

`content_hash` 当前主要用于文档级去重。

我们的二次开发需要补强的是 chunk 级 hash：

```text
chunk.metadata.content_hash
```

### 8.2 向量库支持 `upsert/delete`

位置：

`lightrag/base.py`

向量存储抽象里有：

```python
upsert(data)
delete(ids)
```

所以 chunk 增量更新可以映射为：

```text
added/modified -> chunks_vdb.upsert(...)
deleted -> chunks_vdb.delete(chunk_ids)
```

### 8.3 删除链路已有参考

位置：

`lightrag/lightrag.py`

`adelete_by_doc_id()` 已经实现了文档维度删除。

源码里能看到删除 chunk 时会调用：

```python
self.chunks_vdb.delete(chunk_ids)
self.text_chunks.delete(chunk_ids)
```

这说明我们后续做源码接入时，应该复用它的删除和 KG purge（知识图谱清理）思想，而不是只在 JSON 文件里删一行。

## 9. 对最终项目的意义

这个阶段可以成为简历项目里的一个明确亮点：

```text
设计并实现基于 document_id、chunk_id、content_hash、version 的增量索引机制，
在文档更新场景下仅对 added/modified chunks 重新 embedding，
实验中 embedding 重算量从 34 降低到 2，节省 94.12%，同时保持查询一致性。
```

要注意措辞：

当前是实验层原型，不是已经完整接入 LightRAG 核心源码。

更准确的说法是：

```text
完成增量索引原型与消融实验，验证了源码接入方案的可行性。
```

## 10. 本阶段产物

脚本：

`experiments/evaluation/scripts/run_incremental_index_ablation_v0.py`

结果目录：

`experiments/evaluation/results/incremental_index_ablation_v0/`

结果文件：

`incremental_index_ablation_v0_summary.csv`

`incremental_index_ablation_v0_records.csv`

`incremental_index_ablation_v0_actions.csv`

`incremental_index_ablation_v0_query_check.csv`

`incremental_index_ablation_v0_records.jsonl`

`incremental_index_ablation_v0_summary.md`

## 11. 本阶段结论

增量索引必须同时满足两个条件：

```text
省成本
不产生脏数据
```

只省 embedding 不够。

如果不看 `content_hash`，修改不会被发现。

如果不处理 `deleted`，旧知识会继续被检索出来。

如果 `chunk_id` 不稳定，增量索引会退化成整库重建。

所以最终源码接入时，增量索引的核心不是某一个函数，而是一整套一致性机制：

```text
stable chunk_id
+ chunk content_hash
+ version
+ text_chunks upsert/delete
+ chunks_vdb upsert/delete
+ graph/entity/relation attribution cleanup
+ query regression check
```

