---
name: execute
description: TDD 驱动的逐里程碑执行。当用户说"开始执行""执行计划""execute""实现""开始编码""继续执行"时使用此技能。读取 milestones.json 中的里程碑顺序，以"写测试→实现→验证"的 TDD 循环逐个完成，更新结构化状态文件。
version: 2.0.0
---

# TDD 驱动的逐里程碑执行

读取 `.workflow/milestones.json` 中的里程碑序列，以严格的 TDD 循环逐个执行。每个里程碑遵循"写测试 → 实现 → 验证"的节奏。

## 上下文隔离策略

**关键机制**：每个里程碑通过子代理（Agent 工具）执行，完成后子代理上下文自动释放。execute 作为编排者保持精简上下文。

```
execute（编排者）
  ├─ 读取 milestones.json → 定位下一个 pending 里程碑
  ├─ 生成子代理 → 执行 M0 的 TDD 循环 → 返回摘要 → M0 上下文释放
  ├─ 更新 milestones.json + verify.json + events.jsonl
  ├─ 通过 plan_sync export 更新 plan.md
  ├─ 生成子代理 → 执行 M1 的 TDD 循环 → 返回摘要 → M1 上下文释放
  └─ ...直到全部完成
```

## 前置检查

1. 确认 `.workflow/` 目录存在
2. 读取 `workflow.json`，检查：
   - `plan_approved == true`（**强门禁：未经确认不能执行**）
   - `phase` 为 `executing`（如果不是，且 plan_approved，自动推进）
3. 读取 `milestones.json`，确认有里程碑定义
4. 读取 `spec.md` 了解项目目标和约束
5. 加载 `skills/execute/references/` 下的执行规则：
   - `orchestrator-playbook.md` - 编排者职责与失败处理
   - `subagent-contract.md` - 子代理输入/输出契约
   - `execution-rules.md` - 范围纪律、记录纪律
   - `tdd-guardrails.md` - TDD 铁律
   - `validation-policy.md` - 验证策略

## 编排者流程

execute 自身只保留流程骨架，详细步骤改由独立 reference 文档约束：

- 编排职责、状态推进、失败处理：`skills/execute/references/orchestrator-playbook.md`
- 子代理输入、禁止事项、返回格式：`skills/execute/references/subagent-contract.md`

编排层必须只做四件事：
- 选里程碑
- 调子代理
- 调 gate
- 写状态

**子代理不直接写 milestones.json / workflow.json / events.jsonl**，只负责编写代码和测试、运行验证。状态更新由编排者根据子代理返回的结果完成。

## 里程碑完成处理（编排者）

### 门禁检查

里程碑完成时，**必须实际执行** `python tools/workflow_gate.py milestone <id>`：
- 依赖全部完成
- 存在 RED 证据
- 测试结果为 green
- 有验证结果
- verify.json 中有通过的验证记录

如果 gate 命令失败，停止推进状态，保留当前里程碑为未完成或阻塞，先修复问题。

### 更新状态文件

1. **milestones.json**：更新里程碑状态为 `completed`，填入 `red_evidence`、`test_result`、`verify_result_summary`、`decision_log`、`completed_at`
2. **verify.json**：追加验证运行记录
3. **events.jsonl**：追加 `milestone_completed` 事件
4. **plan.md**：必须实际执行 `python tools/plan_sync.py export` 重新生成（已完成里程碑折叠为单行）；如果失败则停止推进状态
5. **workflow.json**：更新 `current_milestone_id` 为下一个待执行里程碑
6. **必须实际执行** lint 校验：`python -X utf8 tools/workflow_lint.py --workflow-dir .workflow`；如果 lint 报告任何错误，**当前里程碑视为未完成**，修正后重新执行

## 中断恢复

如果执行被中断，重新调用时：
1. 读取 `milestones.json` 找到第一个 `in_progress` 或 `pending` 里程碑
2. 读取 `workflow.json.current_milestone_id`
3. 从断点继续执行

## 完成摘要

所有里程碑完成后，输出最终报告并更新 `workflow.json`。字段以 `tools/schemas/workflow.schema.json` 为准；此时至少要保证：
- `phase = verifying`
- `current_milestone_id = null`

提示用户运行 `/auto-pilot:verify` 做最终全量检查。

### 最后一步：工作流一致性校验

所有里程碑全部完成后，**必须实际执行**最终 lint：

```bash
python -X utf8 tools/workflow_lint.py --workflow-dir .workflow
```

如果 lint 报告任何错误，**本技能视为未完成**，根据错误信息修正 `.workflow/` 文件后，重新执行 lint 直至零错误。

## 重要约束

- **plan_approved 是强门禁**：未经用户确认不能执行
- **严格 TDD 循环**：先写测试，后写实现，不可颠倒
- **禁止修改测试以通过验证**：这是贯穿整个工作流的铁律
- **一次一个里程碑**：不并行执行多个里程碑
- **范围纪律**：只做里程碑定义的内容，不"顺便"改其他东西
- **门禁不可跳过**：每个里程碑完成前必须通过 gate 检查
- **状态写入 JSON**：不再依赖 Markdown 标题和 emoji 解析状态
