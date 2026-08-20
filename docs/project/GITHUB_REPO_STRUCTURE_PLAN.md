# GitHub Repository Structure Plan

本文档是 `GITHUB_REPO_STRUCTURE_PLAN.md` 的文档区版本，用于说明最终 GitHub 仓库应该如何组织。

## 1. 根目录职责

根目录只保留最重要的入口：

```text
README.md
LICENSE
pyproject.toml
requirements*.txt
lightrag/
experiments/
docs/
examples/
tests/
scripts/
```

根目录不应该堆放学习笔记、草稿和本地运行产物。

## 2. README 职责

README 首页回答：

1. 项目解决什么问题
2. 做了哪些二次开发
3. 有哪些真实实验结果
4. 如何安装和运行
5. 源码入口在哪里
6. 当前局限和后续计划

## 3. docs/project 职责

`docs/project/` 保存二次开发项目的深入文档：

```text
docs/project/
├── README.md
├── LEARNING_NOTES.md
├── SOURCE_CODE_GUIDE.md
├── EXPERIMENT_GUIDE.md
├── ABLATION_SUMMARY.md
├── INCREMENTAL_INDEX_DESIGN.md
├── MULTIMODAL_DESIGN.md
├── INTERVIEW_QA.md
└── GITHUB_REPO_STRUCTURE_PLAN.md
```

## 4. experiments/evaluation 职责

`experiments/evaluation/` 保存真实实验证据：

```text
experiments/evaluation/
├── datasets/
├── scripts/
├── results/
├── evaluation_schema.json
└── *_REPORT.md
```

README 中的指标必须能追溯到这里的脚本和报告。

## 5. 不建议提交的内容

```text
.venv/
__pycache__/
*.pyc
ollama_demo_storage/
lightrag_hku.egg-info/
```

这些是本地运行产物，不适合作为 GitHub 项目内容。

## 6. 后续动作

最终提交前：

- 确认 `README_FINAL.md` 是否替换为 `README.md`
- 检查 `.gitignore`
- 检查关键脚本是否可运行
- 保留实验结果证据
- 保留 HKUDS/LightRAG 致谢
