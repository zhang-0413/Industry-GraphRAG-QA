# 阶段 8.9：Metadata Filter 消融实验报告

## 1. 本阶段做了什么

本阶段验证 Metadata Filter（元数据过滤）对多模态 RAG 的作用。

前面我们已经把 PDF 中的 table（表格）和 image（图片）解析成了不同 `content_type`（内容类型）的 chunk：

```text
text chunk
table chunk
image chunk
```

本阶段要回答的问题是：

```text
当用户明确问表格或图片时，
先按 content_type 过滤候选 chunk，
是否能减少噪声、提升上下文质量？
```

## 2. 为什么需要 metadata filter

如果不做过滤，检索空间是：

```text
text + table + image 全部混在一起
```

例如用户问：

```text
What is the measured pressure of Pipeline-7A in the inspection table?
```

如果不做 filter，系统可能返回：

```text
table chunk + text chunk + text chunk + image chunk + text chunk
```

虽然第一个 chunk 可能已经命中，但后面很多上下文是噪声。

如果做 filter：

```text
target_content_types = ["table"]
```

系统只在表格 chunk 中查。

这能减少：

1. 无关上下文。
2. LLM 输入 token。
3. Rerank 候选数量。
4. 表格/图片问题被普通文本干扰的风险。

## 3. 实验设置

评测集：

`experiments/evaluation/datasets/eval_v0_20.jsonl`

重点子集：

| sample_id | question_type | target_content_types |
| --- | --- | --- |
| EVAL-0016 | table | table |
| EVAL-0017 | table | table |
| EVAL-0018 | image | image |
| EVAL-0020 | multi_hop | table + image |

使用的真实知识库：

```text
storage_structure_aware
storage_multimodal
```

总候选空间：

```text
14 chunks = 11 text chunks + 3 multimodal chunks
```

## 4. 对比策略

| Strategy（策略） | 含义 |
| --- | --- |
| `bm25_unfiltered` | BM25 在全部 chunk 中检索 |
| `bm25_metadata_filtered` | 先按 content_type 过滤，再 BM25 |
| `vector_unfiltered` | 向量检索全部 chunk |
| `vector_metadata_post_filter` | 向量检索后按 content_type 后过滤 |
| `bm25_vector_rrf_unfiltered` | BM25 + Vector + RRF，不过滤 |
| `bm25_vector_rrf_metadata_filtered` | BM25/Vector 都按 content_type 过滤后再 RRF |
| `router_metadata_filter` | Router 判断是否需要 metadata filter |

注意：

当前实验里的向量过滤是 post-filter（后过滤）：

```text
vector search all
-> filter by content_type
```

更理想的生产实现是 pre-filter（前过滤）：

```text
vector search where content_type in [...]
```

这需要向量数据库本身支持 metadata 条件过滤。

## 5. 多模态子集结果

这是本阶段最重要的结果。

| Strategy | Hit@5 | Recall@5 | MRR | Context Precision | Content Type Precision | Candidate Space Reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `bm25_metadata_filtered` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9107 |
| `vector_metadata_post_filter` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9107 |
| `bm25_vector_rrf_metadata_filtered` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9107 |
| `router_metadata_filter` | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.9107 |
| `bm25_unfiltered` | 1.0000 | 1.0000 | 1.0000 | 0.2500 | 0.2500 | 0.0000 |
| `vector_unfiltered` | 1.0000 | 1.0000 | 1.0000 | 0.2500 | 0.2500 | 0.0000 |
| `bm25_vector_rrf_unfiltered` | 1.0000 | 1.0000 | 1.0000 | 0.2500 | 0.2500 | 0.0000 |

## 6. 人话解释

### 6.1 为什么 Recall 没变

多模态子集里，不过滤和过滤后的 Recall@5 都是 1.0。

这说明在当前小数据集里，正确的 table/image chunk 本来就能被召回。

所以 metadata filter 的价值不是“从找不到变成找得到”，而是：

```text
从找到正确证据 + 带很多噪声
变成只带正确类型的证据
```

### 6.2 为什么 Context Precision 大幅提升

以 EVAL-0016 表格题为例。

不做过滤时：

```text
content_types = table | text | text | text | text
context_precision = 0.2
```

做过滤后：

```text
content_types = table
context_precision = 1.0
```

这说明未过滤检索虽然命中了表格，但 Top-5 中有 4 个 chunk 都不是目标类型。

对 LLM 来说，这些就是额外噪声。

### 6.3 multi_hop 跨模态题为什么适合 table + image filter

EVAL-0020 的问题是：

```text
According to the table and diagram,
what was Pipeline-7A's pressure status
and where was ReliefValve-RV9 installed?
```

它需要两个证据：

```text
table chunk: Pipeline-7A pressure status
image chunk: ReliefValve-RV9 installation position
```

不做过滤时：

```text
content_types = image | table | text | text | text
context_precision = 0.4
```

做过滤后：

```text
content_types = image | table
context_precision = 1.0
```

这就是多模态 Router 应该输出多个 target content types 的原因：

```text
target_content_types = ["table", "image"]
```

## 7. 全量 20 问结果

| Strategy | Hit@5 | Recall@5 | MRR | Context Precision |
| --- | ---: | ---: | ---: | ---: |
| `bm25_metadata_filtered` | 1.0000 | 0.9625 | 1.0000 | 0.4000 |
| `bm25_unfiltered` | 1.0000 | 0.9375 | 1.0000 | 0.2400 |
| `bm25_vector_rrf_metadata_filtered` | 1.0000 | 0.9625 | 1.0000 | 0.4000 |
| `bm25_vector_rrf_unfiltered` | 1.0000 | 0.9625 | 1.0000 | 0.2500 |
| `router_metadata_filter` | 1.0000 | 0.9625 | 1.0000 | 0.4000 |
| `vector_metadata_post_filter` | 1.0000 | 0.9625 | 0.9250 | 0.4000 |
| `vector_unfiltered` | 1.0000 | 0.9625 | 0.9000 | 0.2500 |

全量结果也说明：

```text
metadata filter 主要提升 Context Precision
```

但要注意，当前全量评测集较小，且 text/table/image 的 chunk 数量不均衡，所以不能把这个结论直接泛化到大规模知识库。

## 8. 和前面实验的关系

阶段 8.5 Rerank 消融说明：

```text
rerank 能修复排序问题，但错误 rerank 会伤害简单题
```

阶段 8.6 Query Router 消融说明：

```text
Router 应该决定什么时候用复杂策略
```

阶段 8.9 Metadata Filter 进一步说明：

```text
Router 不只应该选择 BM25 / Vector / Graph / Rerank
还应该选择 content_type 过滤条件
```

完整链路应该是：

```text
User Query
-> Query Router
-> decide retrieval strategy
-> decide metadata_filter
-> retrieve candidates
-> optional rerank
-> final context
-> LLM answer
```

## 9. 对源码接入的启发

后续二次开发时，建议让 `QueryParam` 或新扩展参数支持：

```python
QueryParam(
    mode="hybrid",
    top_k=5,
    metadata_filter={
        "content_type": ["table", "image"],
        "document_id": ["doc_004_pipeline_inspection"],
    },
)
```

或由 Router 输出：

```json
{
  "route": "table_image_join",
  "selected_strategy": "bm25_vector_rrf",
  "metadata_filter": {
    "content_type": ["table", "image"]
  },
  "final_top_k": 5,
  "use_rerank": false
}
```

需要注意：

1. BM25 可以很容易做 pre-filter，因为它直接操作 chunk 列表。
2. Vector Store 最好使用支持 metadata filter 的数据库，例如 Qdrant、Milvus、Weaviate、Postgres pgvector。
3. Graph Store 需要更谨慎，因为实体/关系本身未必有 `content_type`，通常要通过 `source_id` 回到 chunk metadata 再过滤。

## 10. 本阶段产物

脚本：

`experiments/evaluation/scripts/run_metadata_filter_ablation_v0.py`

结果目录：

`experiments/evaluation/results/metadata_filter_ablation_v0/`

结果文件：

`metadata_filter_ablation_v0_summary.csv`

`metadata_filter_ablation_v0_multimodal_summary.csv`

`metadata_filter_ablation_v0_records.csv`

`metadata_filter_ablation_v0_records.jsonl`

`metadata_filter_ablation_v0_summary.md`

## 11. 本阶段结论

Metadata Filter 的主要价值是：

```text
减少错误类型 chunk 进入 context
提升 Context Precision
降低后续 LLM 和 rerank 的噪声
```

在本实验中，多模态子集：

```text
Context Precision: 0.25 -> 1.00
Content Type Precision: 0.25 -> 1.00
Candidate Space Reduction: 91.07%
Recall@5: 保持 1.00
```

所以最终项目里，多模态 RAG 不应该只依赖 embedding 相似度。

更稳的做法是：

```text
先用 Router 判断问题模态
再用 metadata filter 限定 content_type
最后再做 BM25 / Vector / RRF / Rerank
```

