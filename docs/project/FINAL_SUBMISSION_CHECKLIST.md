# Final GitHub Submission Checklist

本文档用于阶段 9.6：最终 GitHub 提交前检查。

## 1. 当前提交目标

本项目当前不建议直接把所有本地产物提交到 GitHub。

推荐提交的是：

```text
README_FINAL.md
docs/project/
experiments/evaluation/
.gitignore
```

其中：

- `README_FINAL.md` 是最终首页候选。
- `docs/project/` 是二次开发文档区。
- `experiments/evaluation/` 是实验数据、脚本和报告证据。
- `.gitignore` 用于排除本地运行产物。

## 2. 应该提交的内容

### README 和项目文档

| 文件/目录 | 是否提交 | 说明 |
| --- | --- | --- |
| `README_FINAL.md` | 是 | 最终可替换根目录 `README.md` 的候选版本 |
| `docs/project/README.md` | 是 | 二次开发文档区入口 |
| `docs/project/LEARNING_NOTES.md` | 是 | 学习路线总结 |
| `docs/project/SOURCE_CODE_GUIDE.md` | 是 | 源码导读 |
| `docs/project/EXPERIMENT_GUIDE.md` | 是 | 实验运行指南 |
| `docs/project/ABLATION_SUMMARY.md` | 是 | 消融实验总结 |
| `docs/project/INCREMENTAL_INDEX_DESIGN.md` | 是 | 增量索引设计 |
| `docs/project/MULTIMODAL_DESIGN.md` | 是 | 多模态设计 |
| `docs/project/INTERVIEW_QA.md` | 是 | 面试题和参考答案 |
| `docs/project/GITHUB_REPO_STRUCTURE_PLAN.md` | 是 | 仓库结构规划 |
| `docs/project/FINAL_SUBMISSION_CHECKLIST.md` | 是 | 当前提交检查清单 |

### 实验文件

| 路径 | 是否提交 | 说明 |
| --- | --- | --- |
| `experiments/evaluation/datasets/` | 是 | 评测集 |
| `experiments/evaluation/scripts/` | 是 | 实验脚本 |
| `experiments/evaluation/*.md` | 是 | 实验报告 |
| `experiments/evaluation/evaluation_schema.json` | 是 | 评测 schema |
| `experiments/evaluation/results/` | 条件提交 | 建议提交关键结果表，避免提交过大的临时文件 |

## 3. 不应该提交的内容

| 文件/目录 | 原因 |
| --- | --- |
| `.venv/` | 本地 Python 虚拟环境 |
| `__pycache__/` | Python 缓存 |
| `*.pyc` | Python 编译缓存 |
| `ollama_demo_storage/` | 本地 LightRAG Demo 存储 |
| `lightrag_hku.egg-info/` | 本地 editable install 生成信息 |
| 大型临时日志 | 与复现实验无关 |

当前已在 `.gitignore` 中确认：

```gitignore
.venv/
__pycache__/
*.py[cod]
*.egg-info/
ollama_demo_storage/
```

## 4. 待确认的根目录草稿文件

当前根目录有三个 README 草稿层级：

| 文件 | 建议 |
| --- | --- |
| `PROJECT_README_DRAFT.md` | 可移动到 `docs/project/LEARNING_README_DRAFT.md`，或最终不提交 |
| `PROJECT_README_GITHUB.md` | 可移动到 `docs/project/README_GITHUB_DRAFT.md`，或最终不提交 |
| `README_FINAL.md` | 最终建议改名为 `README.md` |

当前阶段暂不移动这些文件，避免误覆盖原版 LightRAG README。

## 5. 最终替换 README 的建议

如果你准备创建一个个人二次开发仓库，而不是继续保留原版 LightRAG 首页，可以执行：

```powershell
Copy-Item README.md README_LIGHTRAG_ORIGINAL.md
Copy-Item README_FINAL.md README.md
```

含义：

- `README_LIGHTRAG_ORIGINAL.md`：保留原版 LightRAG README 备份。
- `README.md`：替换成你的二次开发项目首页。

如果你只是 fork 原版 LightRAG 并希望保持上游首页，则不要替换 `README.md`，只保留 `README_FINAL.md`。

## 6. 提交前建议运行的检查命令

查看 Git 状态：

```powershell
git status --short
```

检查忽略规则：

```powershell
git check-ignore -v ollama_demo_storage/
```

检查评测集：

```powershell
python experiments/evaluation/scripts/validate_dataset.py
python experiments/evaluation/scripts/validate_dataset_evidence.py
```

快速运行关键实验：

```powershell
python experiments/evaluation/scripts/run_retrieval_eval_v0.py
python experiments/evaluation/scripts/merge_stage8_final_table_v0.py
```

## 7. 推荐提交命令

如果你确认要提交当前二次开发成果，可以先只添加关键文件：

```powershell
git add .gitignore
git add README_FINAL.md
git add docs/project
git add experiments/evaluation
```

然后查看暂存内容：

```powershell
git status --short
```

提交：

```powershell
git commit -m "Add industry GraphRAG experiments and project docs"
```

## 8. 推荐 PR / Commit 描述

```text
Add project README, documentation, evaluation dataset, and ablation experiments for a complex industry document GraphRAG QA system.

Highlights:
- Add structure-aware chunking design and ablation summary
- Add BM25 / Vector / Graph retrieval comparison
- Add BM25 + Vector + RRF hybrid retrieval experiments
- Add Query Router and conditional rerank ablations
- Add metadata filter experiments for table/image questions
- Add incremental index design and ablation experiment
- Add evaluation dataset and retrieval/answer/judge reports
```

## 9. 当前风险

- `experiments/evaluation/results/` 可能包含较多中间结果，提交前应检查大小。
- 当前 README 指标来自 20 条小型评测集，不能包装成大规模 benchmark。
- 多模态部分仍是模拟 chunk，不能说已经完整支持真实 PDF 图片问答。
- 还没有把成熟模块正式接入 `lightrag/` 核心源码，当前主要是实验验证。

## 10. 阶段 9.6 结论

当前项目已经具备 GitHub 展示的基础条件：

```text
README 首页候选
+ docs/project 文档区
+ experiments/evaluation 实验证据
+ .gitignore 本地产物过滤
```

下一步可以进入阶段 9.7：

```text
检查实验文件大小和 Git 暂存策略
-> 决定是否替换 README.md
-> 准备最终提交命令
```
