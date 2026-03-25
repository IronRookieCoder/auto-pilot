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
      │
      │  第一步：检查 status 字段
      ├─ status=blocked/failed/paused → 向用户展示 reason，询问如何处理：
      │    ├─ 用户要求重试 → 将 status 设为 running，从当前 phase 继续
      │    ├─ 用户要求回退 → 根据用户指示调整
      │    └─ 用户无明确指示 → 不继续执行，等待用户决策
      │
      │  第二步：status=running 时，按 phase 分派
      ├─ phase=init, spec_approved=false → 提示用户审阅并确认 spec
      ├─ phase=planning, plan_approved=false → 提示用户审阅并确认 plan
      ├─ phase=executing → 读取 milestones.json，从断点继续 execute
      ├─ phase=verifying → 运行最终 verify
      └─ phase=completed → 输出完成报告
```

**不再依赖 Markdown 标题和 emoji 判断状态**，只读 workflow.json 的 `phase` 和 `status` 两个字段。

## 执行流程

### 上下文隔离

run 作为顶层编排者，每个阶段通过子代理执行，阶段完成后上下文自动释放：

```
run（编排者，只做状态检测、阶段调度和人工门禁交互）
  ├─ 子代理: init → 完成, 上下文释放
  ├─ run 自身: lint 检查
  ├─ run 自身: [PAUSE] spec.md 用户确认（第一个人工门禁）+ workflow_confirm.py spec
  ├─ 子代理: plan → 完成, 上下文释放
  ├─ run 自身: lint 检查
  ├─ run 自身: [PAUSE] plan.md 用户确认（第二个人工门禁）+ workflow_confirm.py plan
  ├─ execute（直接执行，内部再按里程碑生成子代理）
  ├─ run 自身: lint 检查
  ├─ 子代理: verify（最终全量检查）→ 完成, 上下文释放
  └─ run 自身: lint 检查 + 生成完成报告
```

init 和 plan 产出全部写入 .workflow/ 文件，下一阶段从文件读取，不依赖上下文传递。

### 阶段 1：初始化（init）

如果 `.workflow/` 不存在：

1. 从用户输入中提取项目需求描述（用户调用 run 时应提供需求）
2. 执行 init 技能的完整流程
3. 使用用户提供的需求直接填充 spec.md
4. 生成 workflow.json、milestones.json、verify.json、events.jsonl
5. 执行 lint 检查：`python -X utf8 tools/workflow_lint.py --workflow-dir .workflow`
   - lint 失败 → 根据错误信息修正 `.workflow/` 文件，重新 lint 直至零错误

**如果用户没有提供需求描述**：询问用户提供需求，不继续执行。

**如果 init 子代理执行失败**：向用户报告失败原因，不继续执行。

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
   - 如果命令失败，向用户报告错误信息，停止流程，不得手写状态推进

### 阶段 2：规划（plan）

1. 执行 plan 技能的完整流程
2. 输出里程碑概览
3. 执行 lint 检查：`python -X utf8 tools/workflow_lint.py --workflow-dir .workflow`
   - lint 失败 → 根据错误信息修正，重新 lint 直至零错误

**如果 plan 子代理执行失败**：向用户报告失败原因，不继续执行。

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
   - 如果命令失败，向用户报告错误信息，停止流程，不得手写状态推进

### 阶段 3：执行（execute）

1. 执行 execute 技能的完整流程
2. 逐里程碑 TDD 循环：写测试 → 实现 → 验证
3. 每个里程碑完成后更新结构化状态文件
4. 所有里程碑完成后执行 lint 检查：`python -X utf8 tools/workflow_lint.py --workflow-dir .workflow`
   - lint 失败 → 根据错误信息修正，重新 lint 直至零错误
5. 进入收尾阶段

**如果某个里程碑执行失败**：execute 技能会将该里程碑标记为 failed 并停止推进。run 收到失败结果后，向用户报告失败的里程碑及原因，等待用户决策（修复后重试 / 跳过 / 终止）。

### 阶段 4：收尾（verify）

1. 推进 `workflow.json.phase` 到 `verifying`
2. 运行最终全量验证：调用 verify 技能，指定 scope=final，执行完整的 lint → typecheck → test → build 验证链
3. 验证通过 → 更新 `workflow.json.final_verify_overall = "pass"`
4. 执行 lint 检查：`python -X utf8 tools/workflow_lint.py --workflow-dir .workflow`
   - lint 失败 → 根据错误信息修正，重新 lint 直至零错误
5. 推进 `workflow.json.phase` 到 `completed`
6. 生成完成报告

**如果最终验证失败**：verify 技能内部会尝试最多 3 轮自动修复。如果 3 轮后仍未通过，run 向用户报告失败的验证步骤和错误信息，设置 `workflow.json.final_verify_overall = "fail"`，不推进到 completed，等待用户决策。

## 完成报告

```
工作流完成

[最终统计]
- 里程碑：{N}/{N} 完成
- 测试：{N} 通过
- 验证：全部通过

[项目文件]
- .workflow/spec.md           - 项目规格（冻结）
- .workflow/plan.md           - 里程碑计划（人工审阅视图）
- .workflow/workflow.json     - 工作流状态
- .workflow/milestones.json   - 里程碑详情
- .workflow/verify.json       - 验证记录
- .workflow/events.jsonl      - 事件日志
```

## 中断恢复

工作流可以在任何时候被中断，重新调用 `/auto-pilot:run` 时：

1. 读取 `workflow.json` 的 `phase` 和 `status` 字段确定当前阶段和状态
2. 如果 `status` 为 `blocked`/`failed`/`paused`，先向用户展示 `reason` 并等待决策
3. 根据结构化状态精确恢复到断点
4. 不会重复已完成的阶段和里程碑

**边界情况处理**：
- 中断发生在 `workflow_confirm.py` 执行前（用户已口头确认但脚本未执行）→ `spec_approved`/`plan_approved` 仍为 false，重新进入门禁确认流程，用户需再次确认
- 中断发生在子代理执行中途 → 子代理的中间产出可能不完整，但 `.workflow/` 状态文件未被更新（子代理不直接写状态文件），因此状态仍然一致，从当前 phase 重新执行即可
- 状态出现不一致（如 lint 检查报错）→ 先执行 `workflow_lint.py`，根据错误信息修正后再继续

## 工作流一致性校验

每个主要阶段（init/plan/execute/verify）完成后，run 编排者**必须实际执行**：

```bash
python -X utf8 tools/workflow_lint.py --workflow-dir .workflow
```

各阶段描述中已标注 lint 检查的具体位置。如果 lint 报告任何错误，**当前阶段视为未完成**，根据错误信息修正 `.workflow/` 文件后，重新执行 lint 直至零错误。不得跳过 lint 或忽略错误继续推进。

## 重要约束

- **两个人工门禁**：spec 确认和 plan 确认，缺一不可
- **不降低标准**：全自动不等于跳过验证或放松 TDD
- **幂等性**：重复调用从断点继续，不会破坏已有工作
- **状态从 JSON 读取**：不解析 Markdown 判断状态
- **需求描述是必需的**：首次运行时用户必须提供需求，否则询问
- **TDD 铁律始终生效**：全自动不意味着可以修改测试
