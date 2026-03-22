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
   - `execution-rules.md` - 范围纪律、记录纪律
   - `tdd-guardrails.md` - TDD 铁律
   - `validation-policy.md` - 验证策略

## 编排者流程

execute 自身作为编排者，执行以下循环：

```
1. 读取 milestones.json → 找到下一个 status=pending 的里程碑
2. 检查依赖是否全部 completed
3. 将里程碑状态更新为 in_progress
4. 更新 workflow.json.current_milestone_id
5. 追加 milestone_started 事件到 events.jsonl
6. 用 Agent 工具生成子代理，传入里程碑执行 prompt（见下文）
7. 子代理返回执行结果（成功/失败/阻塞 + 摘要）
8. 根据结果：
   ├─ 成功 → 运行 workflow-gate → 通过则标记完成
   ├─ 失败/阻塞 → 记录到 events.jsonl，更新 workflow.json.status=blocked
9. 更新 milestones.json（状态、决策、完成时间）
10. 通过等效 plan_sync export 更新 plan.md
11. 回到步骤 1
```

### 子代理 prompt 模板

为每个里程碑生成子代理时，传入以下信息：

```
你正在执行项目 "{项目名称}" 的里程碑 {里程碑 ID}: {名称}。

## 执行规则
{skills/execute/references/execution-rules.md 的完整内容}

## TDD 铁律
{skills/execute/references/tdd-guardrails.md 的完整内容}

## 验证策略
{skills/execute/references/validation-policy.md 的完整内容}

## 里程碑定义
- 验收标准：{从 milestones.json 提取}
- 测试设计：{从 milestones.json 提取}
- 范围：{从 milestones.json 提取}
- 关键文件：{从 milestones.json 提取}
- 验证命令：{里程碑级 verify_commands，如缺失则用 workflow.json 全局命令}

## 项目上下文
- 技术栈：{从 spec.md 提取}

## 你的任务
严格按照 TDD 循环执行此里程碑：
1. 编写测试用例（基于测试设计）
2. 运行测试，确认 RED（记录失败输出作为 red_evidence）
3. 编写实现代码
4. 运行验证（lint + typecheck + test + build）
5. 验证失败时只修改实现代码，禁止修改测试

完成后返回 JSON 格式结果：
{
  "status": "completed | failed | blocked",
  "red_evidence": "RED 阶段测试失败的输出摘要",
  "test_result": "green | red",
  "verify_steps": [...],
  "files_changed": [...],
  "decisions": [...],
  "failure_reason": "如有"
}
```

**子代理不直接写 milestones.json / workflow.json / events.jsonl**，只负责编写代码和测试、运行验证。状态更新由编排者根据子代理返回的结果完成。

## 里程碑完成处理（编排者）

### 门禁检查

里程碑完成时，执行等效于 `python tools/workflow_gate.py milestone <id>` 的检查：
- 依赖全部完成
- 存在 RED 证据
- 测试结果为 green
- 有验证结果
- verify.json 中有通过的验证记录

### 更新状态文件

1. **milestones.json**：更新里程碑状态为 `completed`，填入 `red_evidence`、`test_result`、`verify_result_summary`、`decision_log`、`completed_at`
2. **verify.json**：追加验证运行记录
3. **events.jsonl**：追加 `milestone_completed` 事件
4. **plan.md**：通过 plan_sync export 重新生成（已完成里程碑折叠为单行）
5. **workflow.json**：更新 `current_milestone_id` 为下一个待执行里程碑

## 中断恢复

如果执行被中断，重新调用时：
1. 读取 `milestones.json` 找到第一个 `in_progress` 或 `pending` 里程碑
2. 读取 `workflow.json.current_milestone_id`
3. 从断点继续执行

## 完成摘要

所有里程碑完成后，输出最终报告并更新 workflow.json：

```json
{
  "phase": "verifying",
  "current_milestone_id": null
}
```

提示用户运行 `/auto-pilot:verify` 做最终全量检查。

## 重要约束

- **plan_approved 是强门禁**：未经用户确认不能执行
- **严格 TDD 循环**：先写测试，后写实现，不可颠倒
- **禁止修改测试以通过验证**：这是贯穿整个工作流的铁律
- **一次一个里程碑**：不并行执行多个里程碑
- **范围纪律**：只做里程碑定义的内容，不"顺便"改其他东西
- **门禁不可跳过**：每个里程碑完成前必须通过 gate 检查
- **状态写入 JSON**：不再依赖 Markdown 标题和 emoji 解析状态
