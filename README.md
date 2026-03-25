# Auto-Pilot：长周期 TDD 编码工作流插件

Auto-Pilot 是一个专为长任务设计的 Claude Code 插件。它将工作流状态持久化到 `.workflow/` 目录，通过结构化状态机、TDD 节奏和强制门禁来保证 AI 执行过程的可控性与可追溯性。

## 安装

将 `auto-pilot` 目录放到 Claude Code 可识别的插件目录，或通过以下命令指定：

```bash
claude --plugin-dir ./auto-pilot
```

## 使用方式

### 一键运行

```text
/auto-pilot:run 实现一个 TODO 应用，支持增删改查和分类
```

执行顺序：

```text
init → 用户确认 spec → plan → 用户确认 plan → execute → verify → completed
```

### 分步运行

```bash
/auto-pilot:init
# 编辑 .workflow/spec.md，填写目标与约束
python tools/workflow_confirm.py spec

/auto-pilot:plan
# 审阅 .workflow/plan.md，确认里程碑划分
python tools/workflow_confirm.py plan

/auto-pilot:execute
/auto-pilot:verify
```

### 单独调用

```bash
/auto-pilot:verify   # 随时验证当前代码质量
/auto-pilot:status   # 查看工作流进度
```

## 技能

| 技能      | 命令                  | 说明                                                |
| --------- | --------------------- | --------------------------------------------------- |
| `init`    | `/auto-pilot:init`    | 初始化 `.workflow/` 目录和项目记忆                  |
| `plan`    | `/auto-pilot:plan`    | 基于 `spec.md` 生成里程碑计划                       |
| `execute` | `/auto-pilot:execute` | 按 TDD 节奏逐里程碑执行                             |
| `verify`  | `/auto-pilot:verify`  | 执行 lint/typecheck/test/build 并写入 `verify.json` |
| `status`  | `/auto-pilot:status`  | 汇总当前工作流状态与进度                            |
| `run`     | `/auto-pilot:run`     | 一键编排 init → plan → execute → verify             |

---

## 阶段流转

```text
init --[spec_approved]--> planning --[plan_approved]--> executing --> verifying --[final_verify=pass]--> completed
```

## TDD 节奏

每个里程碑根据 `tdd_type` 按不同策略推进：

- **`standard`**（默认）：定义测试 → 确认 RED → 编写实现 → 验证 GREEN → 通过门禁 → 标记完成
- **`setup`**：执行搭建 → 验证环境可用 → 通过门禁（RED 证据可选）
- **`verification_only`**：运行验证 → 确认结果 → 通过门禁（RED 证据可选）

> 测试失败时只允许修改实现代码，禁止通过修改测试来强行"通过"验证。

## 中断恢复

工作流支持从已保存的结构化状态中断点恢复：

- `run` / `execute` 读取 `workflow.json` 中的 `phase` 字段，从上次中断的阶段继续
- 当 `status=blocked/failed/paused` 时，必须先执行 `python tools/workflow_resume.py`
- `execute` 优先读取 `current_milestone_id` 恢复当前里程碑；只要存在未处理的 failed 里程碑，就不会继续下一个 pending
- 已完成的里程碑不会被重复执行

---

## 核心设计原则

- 面向人的文档保留为 Markdown：`spec.md`（目标与约束）、`plan.md`（执行计划）
- 面向机器的状态全部结构化：`workflow.json`、`milestones.json`、`verify.json`、`events.jsonl`
- `spec_approved` 和 `plan_approved` 这两个门禁只能由用户手动确认触发
- 只有 `final_verify_overall=pass` 时才允许进入 `completed` 阶段
- `blocked/failed/paused -> running` 只能通过 `workflow_resume.py`
- 关键状态变更必须经过脚本校验，而不仅仅依赖提示词约束

## 目录结构

```text
.workflow/
├── spec.md              # 人工审阅：冻结后的目标、范围与约束
├── plan.md              # 人工审阅：由 milestones.json 自动生成
├── workflow.json        # 状态权威源：全局阶段、门禁与验证命令
├── milestones.json      # 状态权威源：里程碑结构与执行状态
├── verify.json          # 状态权威源：验证运行记录
└── events.jsonl         # 状态权威源：追加式事件流
```

## 工具脚本

| 脚本                                           | 用途                                                        |
| ---------------------------------------------- | ----------------------------------------------------------- |
| `python tools/workflow_init.py`                | 读取 `tools/schemas/*.json`，生成初始化的 `.workflow/` 文件 |
| `python tools/workflow_lint.py [phase]`        | 校验 schema、阶段前置条件及跨文件一致性；warning 不阻断     |
| `python tools/workflow_gate.py milestone <id>` | 里程碑完成门禁：检查依赖、RED 证据、GREEN 结果、验证记录    |
| `python tools/plan_sync.py export`             | 将 `milestones.json` 导出为 `plan.md`                       |
| `python tools/plan_sync.py import`             | 将 `plan.md` 导入回 `milestones.json`，包含 `tdd_type`/`test_files` |
| `python tools/workflow_confirm.py spec`        | 用户确认 `spec.md`，工作流推进到 `planning` 阶段            |
| `python tools/workflow_confirm.py plan`        | 用户确认 `plan.md`，先执行 import + lint，再推进到 `executing` |
| `python tools/workflow_resume.py`              | 恢复 `blocked/failed/paused` 的工作流，先做 lint 与恢复前校验 |

## Schema 定义

结构化状态文件的唯一权威定义见 [`tools/schemas/README.md`](tools/schemas/README.md)：

- [`workflow.schema.json`](tools/schemas/workflow.schema.json)
- [`milestones.schema.json`](tools/schemas/milestones.schema.json)
- [`verify.schema.json`](tools/schemas/verify.schema.json)
- [`event.schema.json`](tools/schemas/event.schema.json)

`workflow_init.py` 直接读取这些 schema 来派生初始 JSON，无需维护平行的硬编码结构。

## 保护钩子

仓库包含 [`hooks/hooks.json`](hooks/hooks.json)，定义了两类自动保护：

- **`PreToolUse`**：调用 [`hooks/validate_workflow_write.py`](hooks/validate_workflow_write.py)
  - 拦截对 `.workflow/*.json`、`events.jsonl`、`plan.md` 的非法直接写入
  - `spec_approved` / `plan_approved` 不允许在首次创建或后续编辑时被 AI 直接写为 `true`
  - `plan.md` 不允许手动编辑，必须通过 `plan_sync.py export` 生成

- **`PostSkill`**：调用 [`hooks/post_skill_lint.py`](hooks/post_skill_lint.py)
  - 在 `init / plan / execute / verify / run` 每次结束后自动运行 `workflow_lint.py`
  - 若产物存在不一致，则阻断后续推进
