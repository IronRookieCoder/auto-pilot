---
name: init
description: 初始化长周期编码工作流的项目记忆系统。当用户说"初始化工作流""创建工作流""init workflow""开始新项目""设置项目记忆"时使用此技能。创建 .workflow/ 目录，生成结构化状态文件和人工审阅文件，为 AI 编码代理的持续工作建立"外部大脑"。
version: 2.0.0
---

# 初始化项目记忆

在当前项目根目录创建 `.workflow/` 目录，生成结构化状态文件（JSON）和人工审阅文件（Markdown），建立 AI 编码代理的持久化"外部大脑"。

## 目标架构

```
.workflow/
├── spec.md              # 人工审阅 - 冻结的项目目标和约束
├── plan.md              # 人工审阅 - 里程碑计划（由 milestones.json 投影生成）
├── workflow.json        # 机器真相源 - 工作流总状态
├── milestones.json      # 机器真相源 - 里程碑结构与执行状态
├── verify.json          # 机器真相源 - 验证结果
└── events.jsonl         # 机器真相源 - 事件流
```

## 执行步骤

### 1. 前置检查

- 确认当前工作目录是项目根目录（存在 package.json / pyproject.toml / go.mod / Cargo.toml 等项目标识文件，或用户明确指定）
- 如果 `.workflow/` 已存在，提示用户：目录已存在，是否要重新初始化（会覆盖现有文件）

### 2. 收集项目信息

通过以下方式收集（优先自动检测，不足时询问用户）：

| 信息项 | 自动检测方式 | 必需 |
|--------|-------------|------|
| 项目名称 | package.json 的 name / 目录名 | 是 |
| 技术栈 | 检测 package.json / pyproject.toml / go.mod 等 | 是 |
| 项目目标 | 询问用户或从用户输入提取 | 是 |
| 验证命令 | 从 package.json scripts / Makefile 等提取 | 是（尽力探测） |
| 现有目录结构 | 自动扫描 | 否 |

### 3. 探测验证能力

主动探测项目的验证命令：

| 项目类型 | Lint | TypeCheck | Test | Build |
|----------|------|-----------|------|-------|
| Node/npm | `npm run lint` | `npx tsc --noEmit` | `npm test` | `npm run build` |
| Python | `ruff check .` | `mypy .` | `pytest` | - |
| Go | `golangci-lint run` | （编译即检查） | `go test ./...` | `go build ./...` |
| Rust | `cargo clippy` | （编译即检查） | `cargo test` | `cargo build` |

对于无法探测到的命令，设置为 `null` 并在 `workflow.json` 中标记。如果缺少测试命令，后续 `plan` 阶段必须生成 M0: 测试基础设施。

### 4. 创建结构化状态文件

**必须实际执行** `python tools/workflow_init.py` 生成四个核心状态文件：

```bash
python -X utf8 tools/workflow_init.py --workflow-dir .workflow \
  [--verify-lint "..."] [--verify-typecheck "..."] [--verify-test "..."] [--verify-build "..."]
```

如果命令失败，停止推进，检查原因后重试。`workflow_init.py` 在文件已存在时会跳过（不覆盖用户已有内容）。

权威定义入口（`workflow_init.py` 内部读取，无需手动引用）：
- `tools/schemas/workflow.schema.json`
- `tools/schemas/milestones.schema.json`
- `tools/schemas/verify.schema.json`
- `tools/schemas/event.schema.json`

### 5. 创建人工审阅文件

#### spec.md

读取 `references/spec-template.md` 模板，用收集的项目信息填充。

#### plan.md

不要手写空模板。创建完空的 `milestones.json` 后，**必须实际执行** `python tools/plan_sync.py export` 生成 `plan.md`，确保元数据和投影视图与当前工具链一致。

### 6. 输出结果

向用户展示：
1. 创建的文件列表（区分人工审阅文件和机器状态文件）
2. 验证命令探测结果（标注哪些成功探测、哪些缺失）
3. 下一步指引：
   - "请打开 `.workflow/spec.md` 审阅并完善，确保项目目标、范围和约束准确"
   - "重点检查验收标准：每条标准必须可测试（能用自动化测试或验证命令判定通过/失败）"
   - "确认后运行 `python tools/workflow_confirm.py spec` 或通过 /auto-pilot:run 继续"

### 最后一步：工作流一致性校验

**必须实际执行**：

```bash
python -X utf8 tools/workflow_lint.py --workflow-dir .workflow
```

如果 lint 报告任何错误，**本技能视为未完成**，根据错误信息修正 `.workflow/` 文件后，重新执行 lint 直至零错误。

## 重要约束

- **不要猜测项目目标** - 如果用户没有提供需求描述，必须询问
- **模板内容必须从 references/ 读取** - 不要硬编码 spec 模板
- **保留用户已有的 .workflow/ 内容** - 如果部分文件已存在且有用户自定义内容，提示用户而非覆盖
- **spec.md 是"冻结"文件** - 在初始化后应该由用户确认，后续流程不应随意修改
- **验证命令必须尽力探测** - 缺失的命令显式标记为 null，不留空
- **不再生成 implement.md / documentation.md / changelog.md** - 这些职责已迁移到结构化文件和插件级 references
