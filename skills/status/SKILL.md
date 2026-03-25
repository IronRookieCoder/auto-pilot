---
name: status
description: 查看工作流状态和项目进度。当用户说"查看状态""进度""status""看看进展""项目状态""完成了多少"时使用此技能。从 workflow.json 和 milestones.json 汇总状态，生成进度摘要。可独立调用。
version: 2.0.0
---

# 查看工作流状态

读取 `.workflow/` 目录中的结构化状态文件，生成项目进度摘要。

## 前置检查

- 确认 `.workflow/` 目录存在
- 至少 `workflow.json` 存在（否则提示先运行 init）

## 执行步骤

### 1. 读取结构化状态

从以下文件读取状态（不解析 Markdown）：

- `workflow.json` - 阶段、状态、门禁
- `milestones.json` - 里程碑列表和状态
- `verify.json` - 最近的验证结果
- `events.jsonl` - 最近的事件（读最后 10 条）

### 2. 统计里程碑

从 `milestones.json` 统计：

| 状态 | 计数 |
|------|------|
| completed | N |
| in_progress | N |
| pending | N |
| failed | N |

### 3. 生成进度摘要

```
## 项目进度

总体进度：{已完成}/{总数} ({百分比}%)
[========----] {进度条}

### 工作流状态
- 阶段：{workflow.json.phase}
- 状态：{workflow.json.status}
- spec 确认：{YES/NO}
- plan 确认：{YES/NO}
- 最终验证：{pass/fail/未执行}

### 里程碑状态
| # | 名称 | 状态 | 验证结果 |
|---|------|------|----------|
| M0 | 测试基础设施 | [DONE] completed | pass |
| M1 | 核心模块 | [WIP] in_progress | - |
| M2 | API 层 | [TODO] pending | - |

### 当前里程碑详情
- **名称**：{current_milestone_id} - {标题}
- **验收标准**：{未完成的条数}/{总条数}
- **测试结果**：{red/green/未执行}
- **阻塞项**：{如有}

### 最近事件
{从 events.jsonl 最后 5 条}

### 下一步
- {基于当前状态的建议操作}
```

### 4. 检查测试健康度

如果有 verify.json 中的验证记录：
- 统计最近一次验证的通过/失败步骤
- 如有失败步骤，标记为需要关注

### 5. 查阅历史（按需）

如果需要详细历史信息，从 `events.jsonl` 中查阅。

## 输出格式

直接在终端输出格式化的进度摘要。

## 独立调用模式

如果 `.workflow/workflow.json` 不存在但项目有测试框架，仅输出测试健康度摘要（运行检测到的测试命令）。

## 重要约束

- **只读操作**：status 不修改任何文件
- **从 JSON 读取**：不解析 Markdown 标题和 emoji
- **信息要准确**：从结构化文件解析，不猜测状态
