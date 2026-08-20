# Multimodal RAG Design

本文档说明本项目的多模态 RAG 设计。当前实验使用模拟多模态 chunk，后续计划接入真实 PDF + MinerU。

## 1. 多模态 RAG 的问题

复杂行业文档中常见：

- 普通段落
- 表格
- 图片
- 图纸
- 截图
- 跨页表格
- 图片下方说明文字

如果把所有内容都当普通文本切片，会出现：

- 表格结构丢失
- 图片无法检索
- 页码和章节信息丢失
- 检索到的上下文噪声变多

## 2. 多模态 chunk schema

推荐每个 chunk 保存：

| 字段 | 含义 |
| --- | --- |
| `document_id` | 文档 ID |
| `chunk_id` | chunk ID |
| `file_name` | 文件名 |
| `chapter` | 章节 |
| `section` | 小节 |
| `page_start` | 起始页 |
| `page_end` | 结束页 |
| `content_type` | `text` / `table` / `image` |
| `content` | 可检索文本 |
| `metadata` | 额外信息 |

## 3. 表格如何处理

表格不应该简单压平成一大段无结构文本。

推荐保存：

- 表格标题
- 表头
- 行列关系
- 单元格内容
- 页码
- 所属章节

示例：

```text
content_type: table
content: "Inspection table: Pipeline-7A pressure threshold is 8.2 MPa ..."
metadata: {chapter, section, page_start, page_end}
```

## 4. 图片如何处理

图片本身不能直接被普通 BM25 或文本 embedding 检索。

需要转换为可检索文本：

- OCR 文字
- caption
- VLM description
- 图片标题
- 图注

示例：

```text
content_type: image
content: "Image shows corrosion near Valve-V12 connected to Pipeline-7A ..."
metadata: {page_start, bbox, image_path}
```

## 5. Metadata Filter

当问题明显是表格题：

```text
content_type=table
```

当问题明显是图片题：

```text
content_type=image
```

这样可以先缩小候选范围，再做 BM25 / Vector / RRF。

## 6. 实验结果

多模态子集：

| Method | Context Precision | Content Type Precision |
| --- | ---: | ---: |
| unfiltered | 0.25 | 0.25 |
| metadata filtered | 1.0 | 1.0 |

结论：

```text
Metadata Filter 的主要作用是减少噪声，而不是凭空创造召回能力。
```

## 7. MinerU 接入计划

后续接入真实 PDF 时，计划链路：

```text
PDF
-> MinerU
-> markdown / layout blocks
-> heading hierarchy
-> paragraph / table / image blocks
-> structure-aware chunk
-> metadata
-> BM25 / Vector / Graph index
```

关键点：

- 保留标题层级
- 保留页码
- 保留表格结构
- 保留图片路径和描述
- 为每个 chunk 生成稳定 `chunk_id`
- 为每个 chunk 生成 `content_hash`

## 8. 当前局限

- 当前实验中的表格和图片是模拟 chunk。
- 尚未接入真实 MinerU。
- 尚未接入真实 OCR / VLM。
- 图片和图纸类问题还需要更完整的视觉理解模型。
