# Changelog

所有重要变更按版本记录。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

---

## v3.0.1 — 2026-03-22

> 修复写保护绕过、gate 异常崩溃、lint 里程碑验证盲区等 4 项问题。

### 修复

- **hooks/validate_workflow_write.py** — `_is_workflow_file()` 支持相对路径识别（`8b248d0`）
  - 原先只检测 `"/.workflow/"` 子串，`.workflow/workflow.json` 等相对路径被直接放行
  - 改为目录分段匹配，兼容绝对路径和相对路径
- **hooks/validate_workflow_write.py** — Edit 工具对 JSON/JSONL 文件不再跳过校验（`8b248d0`）
  - 新增 `_simulate_edit()`：读取原文件 → 应用 old_string/new_string 差异 → 对编辑后的完整内容做 schema 校验
  - 文件不可读时降级为警告放行（PostSkill lint 兜底）
- **tools/workflow_gate.py** — verify.json 和 workflow.json 增加结构防御（`8b248d0`）
  - 对 `verify.json` 增加 `isinstance(dict)` 和 `runs` 数组类型检查，防止 `AttributeError` 崩溃
  - 对 `workflow.json` 增加 `isinstance(dict)` 前置检查
  - 循环内增加 `isinstance(run, dict)` 防御
  - 异常结构统一转为可操作的 gate error 列表

### 新增

- **tools/workflow_lint.py** — 里程碑级 verify 记录一致性检查（`8b248d0`）
  - 新增 `check_milestone_verify_records()`：检查每个 `status=completed` 的里程碑在 verify.json 中是否有 `scope=milestone` 且 `overall=pass` 的记录
  - 将此检查从 gate（AI 主动调用）上提到 lint（PostSkill hook 自动调用），消除检查盲区

---

## v3.0.0 — 2026-03-22

> 引入 hooks 机制和 schema 驱动初始化，强化工具调用确定性。

### 新增

- **hooks/validate_workflow_write.py** — PreToolUse 写保护钩子（`88bb980`）
  - 拦截 Write/Edit 对 `.workflow/` 目录的写入
  - 对 workflow.json、milestones.json、verify.json 做实时 schema 校验
  - 对 events.jsonl 逐行 JSON 解析 + 事件结构校验
  - 对 plan.md 检查 milestones_revision 元数据
- **hooks/post_skill_lint.py** — PostSkill lint 钩子（`88bb980`）
  - 每个技能执行结束后自动运行 `workflow_lint.py`
  - lint 失败时阻断技能完成，形成"生成后立即校验"闭环
- **hooks/hooks.json** — Claude Code hooks 配置（`88bb980`）
- **tools/workflow_init.py** — schema 驱动的初始化工具（`88bb980`）
  - 从 `tools/schemas/*.json` 读取 schema 定义，自动生成符合结构的初始 JSON 文件
  - 支持 `--project-name` 和 `--verify-commands` 参数

### 增强

- **tools/workflow_gate.py** — milestones.json 结构完整性前置检查（`88bb980`）
  - gate 检查前先验证根结构是否为 `{revision, milestones}` 对象
- **tools/workflow_lint.py** — completed 状态最小证据要求（`88bb980`）
  - `status=completed` 时强制要求 `red_evidence`、`test_result=green`、`completed_at`
- **skills/** — 所有技能文档增加强制 lint 步骤（`88bb980`）

---

## v2.0.0 — 2026-03-22

> 从纯 Markdown 驱动重构为「人审 Markdown + 机器 JSON 真相源」分层架构。

### 新增

- **tools/workflow_lint.py** — 工作流状态校验工具（`4d825c5`）
  - workflow.json / milestones.json / verify.json / events.jsonl 全量 schema 校验
  - 阶段前置条件检查（spec_approved → planning、plan_approved → executing）
  - plan.md 与 milestones.json 一致性检查（revision + checksum）
  - completed 跨文件闭环校验
  - events.jsonl 纳入 lint
- **tools/workflow_gate.py** — 里程碑完成门禁（`4d825c5`）
  - 依赖检查、RED 证据检查、测试结果检查、verify 记录检查、plan_approved 检查
- **tools/plan_sync.py** — plan.md ↔ milestones.json 双向同步（`4d825c5`）
  - export：从 milestones.json 生成 plan.md 投影视图
  - import：从 plan.md 反向合并到 milestones.json（merge 策略保留执行结果字段）
  - checksum 机制防止只读字段被误改
- **tools/workflow_confirm.py** — spec/plan 人工确认网关（`4d825c5`）
  - confirm_plan 前置校验 plan.md 同步状态
- **tools/schemas/** — JSON Schema 权威定义（`4d825c5`）
  - workflow.schema.json、milestones.schema.json、verify.schema.json、event.schema.json
- **skills/execute/references/** — execute 职责拆分为 5 个参考文档（`4d825c5`）
  - orchestrator-playbook.md、subagent-contract.md、execution-rules.md、tdd-guardrails.md、validation-policy.md

### 变更

- 全部 6 个 SKILL.md 升级到 v2.0.0 架构（`4d825c5`）
- "执行等效于..."措辞全部改为"**必须实际执行**"（`4d825c5`）
- spec_approved 和 plan_approved 双门禁，只能由用户显式触发（`4d825c5`）
- plan.md 改为 milestones.json 的只读投影视图（`4d825c5`）
- 验证结果写入 verify.json，事件追加到 events.jsonl（`4d825c5`）

### 删除

- skills/init/references/ 下的旧模板：changelog-template.md、documentation-template.md、implement-template.md、plan-template.md（职责迁移到 JSON + references）

---

## v1.0.0 — 2026-03-20

> 初始版本。Claude Code 插件，基于 SKILL.md prompt 驱动的 TDD 工作流。

### 新增

- **插件基础结构**（`6c6d53a`）
  - .claude-plugin/plugin.json 插件配置
  - README.md 项目说明
- **6 个核心技能**（`6c6d53a`）
  - init — 初始化工作流目录和 spec
  - plan — 基于 spec 生成 TDD 里程碑计划
  - execute — TDD 驱动的逐里程碑执行
  - verify — 质量验证与修复
  - status — 查看工作流状态
  - run — 一键全流程编排
- **模板文件**（`6c6d53a`）
  - spec-template.md、plan-template.md、implement-template.md
  - documentation-template.md、changelog-template.md

### 后续补充

- marketplace 配置（`325bb43`）
- 严格模式启用 + 技能配置（`142eea0`）
- spec.md 审阅流程更新（`abc6201`）
- 里程碑模板结构调整（`54f589d`、`8cb1595`）
- 文档管理纪律行数限制规则（`78942d2`）
