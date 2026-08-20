# Project Documentation

本目录保存二次开发项目的说明文档。根目录 `README_FINAL.md` 负责展示项目价值和运行方式，本目录负责解释学习过程、源码入口、实验设计、消融结论和面试准备。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| `LEARNING_NOTES.md` | 从 LightRAG 到二次开发的学习路线 |
| `SOURCE_CODE_GUIDE.md` | LightRAG 核心源码入口和调用链 |
| `EXPERIMENT_GUIDE.md` | 如何运行 baseline、hybrid、router、rerank、metadata、incremental 实验 |
| `ABLATION_SUMMARY.md` | 阶段 8 消融实验总复盘 |
| `INCREMENTAL_INDEX_DESIGN.md` | 增量索引设计：`document_id`、`chunk_id`、`content_hash`、`version` |
| `MULTIMODAL_DESIGN.md` | 多模态 chunk、metadata filter 和后续 MinerU 接入设计 |
| `INTERVIEW_QA.md` | 项目面试题和参考答案 |
| `GITHUB_REPO_STRUCTURE_PLAN.md` | GitHub 仓库最终结构规划 |

## 推荐阅读顺序

```text
README_FINAL.md
-> docs/project/LEARNING_NOTES.md
-> docs/project/SOURCE_CODE_GUIDE.md
-> docs/project/EXPERIMENT_GUIDE.md
-> docs/project/ABLATION_SUMMARY.md
-> docs/project/INTERVIEW_QA.md
```

## 与 experiments/evaluation 的关系

`docs/project/` 是解释层，负责讲清楚为什么这么做。

`experiments/evaluation/` 是证据层，负责保存真实评测集、脚本、结果和报告。

```text
docs/project/
-> tells why and how

experiments/evaluation/
-> contains datasets, scripts and measured results
```
