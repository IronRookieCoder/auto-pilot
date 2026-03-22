# Auto-Pilot：长周期 TDD 编码工作流插件

基于"结构化状态机 + TDD 驱动执行"的 Claude Code 插件，使 AI 编码代理能在长时间任务中保持连贯性和代码质量。

## 核心理念

**人审内容保留 Markdown，机器状态全部结构化。**

通过分层架构构成代理的"外部大脑"：

```
.workflow/
├── spec.md              # 人工审阅 - 冻结的项目目标和约束
├── plan.md              # 人工审阅 - 里程碑计划（由 milestones.json 投影生成）
├── workflow.json        # 机器真相源 - 工作流总状态（阶段/门禁/验证命令）
├── milestones.json      # 机器真相源 - 里程碑结构与执行状态
├── verify.json          # 机器真相源 - 验证结果
└── events.jsonl         # 机器真相源 - 事件流
```

**TDD 铁律贯穿全流程**：测试先行、禁止修改测试以通过验证。

**确定性门禁**：`spec_approved` 和 `plan_approved` 只能由用户确认触发，脚本校验阶段前置条件。

## 技能列表

| 技能 | 命令 | 说明 |
|------|------|------|
| init | `/auto-pilot:init` | 初始化项目记忆，创建 .workflow/ 目录和结构化状态文件 |
| plan | `/auto-pilot:plan` | 基于 spec.md 生成里程碑计划，写入 milestones.json |
| execute | `/auto-pilot:execute` | 读取 milestones.json，逐里程碑 TDD 循环执行 |
| verify | `/auto-pilot:verify` | 质量验证，结果写入 verify.json（可独立调用） |
| status | `/auto-pilot:status` | 从 JSON 汇总状态，生成进度摘要（可独立调用） |
| run | `/auto-pilot:run` | 一键全流程编排，两个人工门禁 |

## 工具脚本

| 脚本 | 用途 |
|------|------|
| `python tools/workflow_lint.py [phase]` | schema 校验 + 阶段前置条件 + MD/JSON 一致性 |
| `python tools/workflow_gate.py milestone <id>` | 里程碑完成门禁（RED 证据 + 测试 + 验证） |
| `python tools/plan_sync.py export` | milestones.json → plan.md |
| `python tools/plan_sync.py import` | plan.md → milestones.json |
| `python tools/workflow_confirm.py spec` | 用户确认 spec，推进阶段 |
| `python tools/workflow_confirm.py plan` | 用户确认 plan，推进阶段 |

## 使用方式

### 全自动（推荐）

```
/auto-pilot:run 实现一个 TODO 应用，支持增删改查和分类功能
```

自动走完 init → spec 确认 → plan → plan 确认 → execute → verify → 完成。

### 分步式

```
/auto-pilot:init                          # 1. 初始化
# 编辑 .workflow/spec.md                   # 2. 完善需求
python tools/workflow_confirm.py spec      # 3. 确认 spec
/auto-pilot:plan                          # 4. 生成计划
# 审阅 .workflow/plan.md                   # 5. 审阅计划
python tools/workflow_confirm.py plan      # 6. 确认 plan
/auto-pilot:execute                       # 7. 逐里程碑执行
/auto-pilot:verify                        # 8. 最终全量验证
```

### 独立调用

```
/auto-pilot:verify        # 随时检查质量
/auto-pilot:status        # 随时查看进度
```

## 阶段流转与门禁

```
init ──[spec_approved]──> planning ──[plan_approved]──> executing ──> verifying ──[final_verify=pass]──> completed
```

- `spec_approved` 和 `plan_approved` 只能由用户确认触发
- `final_verify_overall` 必须为 `pass` 才能进入 `completed`

## TDD 工作流

每个里程碑的执行循环：

```
定义测试 → 确认 RED → 编写实现 → 验证 GREEN → 门禁检查 → 标记完成
    ↑                                    |
    └─── 失败时只改实现，禁止改测试 ←────┘
```

## 中断恢复

工作流支持在任何时刻中断。重新调用 `/auto-pilot:run` 或 `/auto-pilot:execute` 时，从 `workflow.json` 读取结构化状态，精确恢复到断点继续。

## 安装

将 `auto-pilot` 目录放置在 Claude Code 可以识别的插件路径下，或使用：

```bash
claude --plugin-dir ./auto-pilot
```
