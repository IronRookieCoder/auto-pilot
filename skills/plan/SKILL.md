---
name: plan
description: 基于 spec.md 生成 TDD 驱动的里程碑实施计划。当用户说"生成计划""制定计划""plan""拆分任务""规划里程碑"时使用此技能。分析规格说明，拆分为里程碑，输出到 milestones.json，投影生成 plan.md 供人工审阅。
version: 2.0.0
---

# 生成 TDD 驱动的里程碑计划

读取 `.workflow/spec.md`，将项目需求拆分为 TDD 驱动的里程碑序列，写入 `.workflow/milestones.json`，投影生成 `.workflow/plan.md` 供人工审阅。

## 前置检查

1. 确认 `.workflow/spec.md` 存在且内容已填充（不是空模板）
2. 确认 `.workflow/workflow.json` 存在
3. 检查 `workflow.json.spec_approved` 是否为 `true`
   - 如果不是，提示用户先确认 spec：`python tools/workflow_confirm.py spec`
4. 如果 `.workflow/milestones.json` 已有里程碑，提示用户是否覆盖
5. 读取 `workflow.json.verify_commands` 了解项目验证能力

## 核心理念：TDD 驱动的里程碑

每个里程碑的执行顺序是 **测试先行**：

```
定义验收标准 → 设计测试用例 → 明确实现范围 → （execute 阶段执行）
```

里程碑不是"功能列表"，而是"可验证的交付单元"。每个里程碑必须能独立验证通过。

## 执行步骤

### 1. 分析规格说明

读取 `.workflow/spec.md`，提取：
- 功能需求列表
- 非功能需求
- 技术约束
- 验收标准
- 范围边界

### 2. 设计架构概览

基于需求分析，生成：
- 高层架构描述（组件、模块、数据流）
- 关键技术决策及理由
- 用文字或简单 ASCII 图表示架构

### 3. 拆分里程碑

根据项目复杂度拆分里程碑（小型项目 5-10 个，中型 10-15 个，大型 15-25 个），遵循以下原则：

**拆分原则：**
- 每个里程碑是一个可独立验证的交付单元
- 里程碑之间的依赖关系清晰
- 基础设施和核心模块优先
- 渐进式交付：每个里程碑完成后项目处于可工作状态

### 4. 里程碑 0：测试基础设施

检查 `workflow.json.verify_commands`：
- 如果 `test` 命令为 `null`，**第一个里程碑（M0）必须是搭建测试基础设施**
- 即使 `test` 命令存在，如果项目没有测试文件，也应生成 M0

M0 内容：
- 安装测试框架和工具
- 配置测试运行器
- 编写一个 smoke test 确认测试环境工作
- 补全 `workflow.json.verify_commands` 中缺失的命令

### 5. 构建里程碑结构

每个里程碑必须包含以下字段：

```json
{
  "id": "M0",
  "title": "测试基础设施",
  "status": "pending",
  "dependencies": [],
  "acceptance_criteria": ["测试框架安装并可运行", "lint/typecheck/test/build 命令可用"],
  "test_design": ["smoke test：确认测试框架正常运行"],
  "scope": ["搭建测试框架", "配置验证命令"],
  "key_files": ["path/to/config"],
  "verify_commands": {
    "lint": null,
    "typecheck": null,
    "test": null,
    "build": null
  },
  "red_evidence": null,
  "test_result": null,
  "verify_result_summary": null,
  "decision_log": [],
  "completed_at": null
}
```

### 6. 写入 milestones.json

将所有里程碑写入 `.workflow/milestones.json`：

```json
{
  "revision": 1,
  "milestones": [...]
}
```

如果已有 milestones.json，递增 revision。

### 7. 投影生成 plan.md

执行等效于 `python tools/plan_sync.py export` 的操作：
- 从 `milestones.json` 生成 `plan.md`
- 在 `plan.md` 顶部写入 `<!-- milestones_revision: N -->`
- 已完成里程碑折叠为单行摘要
- 当前及待办里程碑保留完整格式

### 8. 更新 workflow.json

```json
{
  "phase": "planning",
  "status": "running",
  "updated_at": "..."
}
```

### 9. 追加事件

向 `events.jsonl` 追加：

```json
{"time": "...", "type": "plan_generated", "phase": "planning", "milestone_id": null, "summary": "生成了 N 个里程碑", "artifacts": {"milestone_count": N}}
```

### 10. 输出摘要

向用户展示：
1. 里程碑列表概览（编号 + 名称 + 依赖关系）
2. 依赖关系图
3. 风险摘要
4. 下一步指引：
   - "请打开 `.workflow/plan.md` 审阅里程碑计划"
   - "确认后运行 `python tools/workflow_confirm.py plan` 或通过 /auto-pilot:run 继续"
   - "**plan 未经确认不能进入执行阶段**"

## 重要约束

- **测试设计是必需项**：每个里程碑必须包含 test_design，没有测试的里程碑不合格
- **不修改 spec.md**：发现规格问题时在输出中提示用户，不自行修改
- **里程碑粒度适中**：太大难以验证，太小浪费开销，单个里程碑的实现时间应在 15-60 分钟
- **验证命令必须具体**：不能写"运行测试"，要写具体命令
- **spec_approved 是前置条件**：spec 未确认不能生成计划
- **milestones.json 是真相源**：plan.md 是投影视图，不是独立真相源
- **plan_approved 由用户触发**：plan 不能自行将 plan_approved 置为 true
