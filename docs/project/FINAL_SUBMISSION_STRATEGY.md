# Final Submission Strategy

本文档用于阶段 9.7：决定最终 GitHub 提交策略。

## 1. 当前有两种提交路线

### 路线 A：保持 LightRAG Fork 风格

特点：

```text
保留原版 README.md
新增 README_FINAL.md
新增 docs/project/
新增 experiments/evaluation/
```

适合情况：

- 你当前仓库仍然是 HKUDS/LightRAG 的 fork。
- 你还想保留上游项目首页和官方说明。
- 你还没准备把它包装成完全独立的个人项目仓库。

优点：

- 不破坏上游 README。
- 后续同步 LightRAG upstream 更清楚。
- 二次开发内容可以通过 `README_FINAL.md` 和 `docs/project/` 展示。

缺点：

- GitHub 默认首页仍然显示原版 LightRAG README。
- 面试官需要你主动说明看 `README_FINAL.md`。

### 路线 B：个人二次开发项目风格

特点：

```text
备份原版 README.md
用 README_FINAL.md 替换 README.md
保留 docs/project/
保留 experiments/evaluation/
```

适合情况：

- 你要创建一个新的个人展示仓库。
- 仓库名称就是你的项目，例如 `Industry-GraphRAG-QA`。
- 你希望 GitHub 首页第一眼展示你的二次开发成果。

优点：

- GitHub 首页就是你的项目介绍。
- 更适合简历和面试展示。
- 访问者不需要再找 `README_FINAL.md`。

缺点：

- 会覆盖原版 LightRAG README。
- 后续如果要同步 upstream，需要注意冲突。

## 2. 当前推荐策略

当前推荐采用：

```text
先路线 A，后路线 B。
```

也就是现在先不覆盖 `README.md`，提交：

```text
.gitignore
README_FINAL.md
docs/project/
experiments/evaluation/
```

等你准备创建个人 GitHub 展示仓库时，再执行 README 替换。

原因：

1. 现在这个目录还是原版 LightRAG 仓库结构。
2. 原版 README 很长，包含官方安装、部署和社区说明，直接覆盖不利于追踪上游。
3. 你的二次开发 README 已经在 `README_FINAL.md` 中完整保存。
4. `docs/project/` 已经提供了完整项目文档区。
5. 未来如果单独建个人项目仓库，再替换 README 更自然。

## 3. 当前建议提交哪些文件

建议提交：

```powershell
git add .gitignore
git add README_FINAL.md
git add docs/project
git add experiments/evaluation
```

暂时不建议提交根目录草稿：

```text
PROJECT_README_DRAFT.md
PROJECT_README_GITHUB.md
GITHUB_REPO_STRUCTURE_PLAN.md
```

原因：

- `PROJECT_README_DRAFT.md` 是学习草稿，内容已经被拆入 `docs/project/`。
- `PROJECT_README_GITHUB.md` 是中间版本，最终已被 `README_FINAL.md` 替代。
- 根目录 `GITHUB_REPO_STRUCTURE_PLAN.md` 已经有文档区版本：`docs/project/GITHUB_REPO_STRUCTURE_PLAN.md`。

## 4. 如果选择路线 A

执行：

```powershell
git add .gitignore
git add README_FINAL.md
git add docs/project
git add experiments/evaluation
git status --short
git commit -m "Add industry GraphRAG project docs and evaluation experiments"
```

提交后，仓库里会保留：

```text
README.md              # LightRAG 原版 README
README_FINAL.md        # 你的项目首页候选
docs/project/          # 你的项目文档
experiments/evaluation # 你的实验和评测证据
```

## 5. 如果选择路线 B

只有当你确认要把这个仓库作为个人二次开发项目首页时，再执行：

```powershell
Copy-Item README.md README_LIGHTRAG_ORIGINAL.md
Copy-Item README_FINAL.md README.md
git add README.md README_LIGHTRAG_ORIGINAL.md README_FINAL.md
git add docs/project
git add experiments/evaluation
git add .gitignore
git commit -m "Prepare README for industry GraphRAG project"
```

提交后，仓库首页会变成你的项目 README。

## 6. 是否需要删除草稿文件

当前不建议用删除命令直接处理，因为这些文件还没有被提交，也不会影响正式提交。

推荐做法：

```text
只 git add 需要提交的文件，不 add 草稿文件。
```

如果后续你想清理根目录，可以再决定：

- 移动到 `docs/project/archive/`
- 或删除
- 或保持未跟踪状态

## 7. 最终 Commit Message 推荐

推荐：

```text
Add industry GraphRAG project docs and evaluation experiments
```

更详细的 commit body：

```text
- Add final project README candidate
- Add docs/project documentation hub
- Add source code guide, experiment guide, ablation summary and interview QA
- Add incremental index and multimodal RAG design docs
- Add evaluation dataset, scripts, reports and experiment results
- Ignore local Ollama demo storage
```

## 8. 阶段 9.7 结论

当前最稳策略：

```text
采用路线 A：
保留原版 README.md，不覆盖；
提交 README_FINAL.md、docs/project/、experiments/evaluation/ 和 .gitignore；
后续创建个人展示仓库时，再用 README_FINAL.md 替换 README.md。
```

这样既保留上游 LightRAG 的完整性，又能完整展示你的二次开发成果。
