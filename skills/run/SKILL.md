---
name: run
description: 一键启动全流程编排。当用户说"一键执行""全自动""run""启动工作流""从头开始""自动完成"时使用此技能。自动检测当前工作流状态，从断点继续或从头开始，依次执行 init → plan → execute 全流程。支持中断恢复。两个人工门禁：spec 确认和 plan 确认。
version: 2.0.0
---

# 全流程自动编排

一键启动完整的 TDD 驱动编码工作流：自动检测状态 → init → plan → execute → verify → 完成。支持中断后重新调用从断点继续。

## 状态检测与恢复

启动时读取 `.workflow/workflow.json` 的结构化状态，决定从哪个阶段开始：

```
检查 .workflow/ 目录
  ├─ 不存在 → 从 init 开始
  ├─ 存在 → 读取 workflow.json
      ├─ phase=init, spec_approved=false → 提示用户审阅并确认 spec
      ├─ phase=planning, plan_approved=false → 提示用户审阅并确认 plan
      ├─ phase=executing → 读取 milestones.json，从断点继续 execute
      ├─ phase=verifying → 运行最终 verify
      └─ phase=completed → 输出完成报告
```

**不再依赖 Markdown 标题和 emoji 判断状态**，只读 workflow.json。

## 执行流程

### 上下文隔离

run 作为顶层编排者，每个阶段通过子代理执行，阶段完成后上下文自动释放：

```
run（编排者，只做状态检测和阶段调度）
  ├─ 子代理: init → 完成, 上下文释放
  ├─ ⏸️ spec.md 用户确认（第一个人工门禁）
  ├─ 子代理: plan → 完成, 上下文释放
  ├─ ⏸️ plan.md 用户确认（第二个人工门禁）
  ├─ execute（直接执行，内部再按里程碑生成子代理）
  └─ 子代理: verify（最终全量检查）→ 完成, 上下文释放
```

init 和 plan 产出全部写入 .workflow/ 文件，下一阶段从文件读取，不依赖上下文传递。

### 阶段 1：初始化（init）

如果 `.workflow/` 不存在：

1. 从用户输入中提取项目需求描述（用户调用 run 时应提供需求）
2. 执行 init 技能的完整流程
3. 使用用户提供的需求直接填充 spec.md
4. 生成 workflow.json、milestones.json、verify.json、events.jsonl

**如果用户没有提供需求描述**：询问用户提供需求，不继续执行。

### 阶段 1.5：spec.md 确认（第一个人工门禁）

init 完成后，**必须暂停等待用户确认 spec.md**，不得自动跳过：

1. 直接提示用户打开 `.workflow/spec.md` 审阅，**不要输出 spec.md 的完整内容、摘录或摘要**
2. 明确提示用户审阅以下重点：
   - 项目目标和范围是否准确
   - 约束条件是否完整
   - 验收标准是否可测试
   - 范围边界是否清晰
3. **等待用户明确确认**（如"确认""没问题""OK""继续"等肯定回复）
4. 如果用户提出修改意见：修改 spec.md → 再次提示审阅 → 再次等待确认
5. 收到确认后，**必须实际执行** `python tools/workflow_confirm.py spec`：
   - 设置 `workflow.json.spec_approved = true`
   - 推进 `workflow.json.phase` 到 `planning`
   - 追加 `spec_approved` 事件到 `events.jsonl`
   - 如果命令失败，停止流程，不得手写状态推进

### 阶段 2：规划（plan）

1. 执行 plan 技能的完整流程
2. 输出里程碑概览

### 阶段 2.5：plan.md 确认（第二个人工门禁）

plan 完成后，**必须暂停等待用户确认 plan.md**：

1. 提示用户打开 `.workflow/plan.md` 审阅里程碑计划
2. 重点检查：
   - 里程碑拆分是否合理
   - 测试设计是否充分
   - 依赖关系是否正确
   - 验收标准是否可测试
3. **等待用户明确确认**
4. 如果用户提出修改：修改 milestones.json → plan_sync export → 再次等待确认
5. 收到确认后，**必须实际执行** `python tools/workflow_confirm.py plan`：
   - 设置 `workflow.json.plan_approved = true`
   - 推进 `workflow.json.phase` 到 `executing`
   - 追加 `plan_approved` 事件到 `events.jsonl`
   - 如果命令失败，停止流程，不得手写状态推进

### 阶段 3：执行（execute）

1. 执行 execute 技能的完整流程
2. 逐里程碑 TDD 循环：写测试 → 实现 → 验证
3. 每个里程碑完成后更新结构化状态文件
4. 所有里程碑完成后进入收尾

### 阶段 4：收尾（verify）

1. 运行最终全量验证（verify 技能，scope=final）
2. 验证通过 → 更新 `workflow.json.final_verify_overall = "pass"`
3. 推进 `workflow.json.phase` 到 `completed`
4. 生成完成报告

## 完成报告

```
🎉 工作流完成

📊 最终统计
- 里程碑：{N}/{N} 完成
- 测试：{N} 通过
- 验证：全部通过

📁 项目文件
- .workflow/spec.md           - 项目规格（冻结）
- .workflow/plan.md           - 里程碑计划（人工审阅视图）
- .workflow/workflow.json     - 工作流状态
- .workflow/milestones.json   - 里程碑详情
- .workflow/verify.json       - 验证记录
- .workflow/events.jsonl      - 事件日志
```

## 中断恢复

工作流可以在任何时候被中断，重新调用 `/auto-pilot:run` 时：

1. 读取 `workflow.json` 确定当前阶段和状态
2. 根据结构化状态精确恢复到断点
3. 不会重复已完成的阶段和里程碑

## 重要约束

- **两个人工门禁**：spec 确认和 plan 确认，缺一不可
- **不降低标准**：全自动不等于跳过验证或放松 TDD
- **幂等性**：重复调用从断点继续，不会破坏已有工作
- **状态从 JSON 读取**：不解析 Markdown 判断状态
- **需求描述是必需的**：首次运行时用户必须提供需求，否则询问
- **TDD 铁律始终生效**：全自动不意味着可以修改测试
