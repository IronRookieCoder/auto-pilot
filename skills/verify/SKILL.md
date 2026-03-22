---
name: verify
description: TDD 驱动的质量验证与修复。当用户说"验证""检查质量""verify""跑测试""运行验证""质量检查"时使用此技能。运行项目的 lint/typecheck/test/build 验证，将结果写入 verify.json。失败时只允许修改实现代码，禁止修改测试用例。可独立调用，不依赖工作流状态。
version: 2.0.0
---

# TDD 驱动的质量验证

运行项目的验证命令（lint/typecheck/test/build），将结果写入 `.workflow/verify.json`。失败项自动修复，**严格遵循 TDD 纪律：只改实现，不改测试**。

## 核心铁律

```
⚠️ 验证失败时，只允许修改实现代码来通过测试。
⚠️ 禁止修改、删除、跳过或弱化任何测试用例。
⚠️ 禁止通过修改测试断言、放宽匹配条件、添加 skip/ignore 来"通过"验证。
⚠️ 如果测试本身确实有 bug，记录为"阻塞"，由用户决定。
```

## 执行步骤

### 1. 识别验证命令

按优先级从以下来源获取验证命令：

1. `.workflow/milestones.json` 中当前里程碑的 `verify_commands`（局部优先）
2. `.workflow/workflow.json` 中的全局 `verify_commands`
3. 项目配置文件自动检测（参见 `skills/execute/references/validation-policy.md`）

如果自动检测失败，询问用户提供验证命令。

### 2. 确定验证范围

- 如果由 execute 调用且指定了里程碑：`scope = "milestone"`，`milestone_id = 指定 ID`
- 如果作为最终全量检查或独立调用：`scope = "final"`，`milestone_id = null`

### 3. 创建验证运行记录

在 `verify.json` 中新增一条 run 记录（如果 `.workflow/` 存在）。run 的字段名和结构必须符合 `tools/schemas/verify.schema.json`，不要在技能文档里维护平行 JSON 样例。

### 4. 按顺序执行验证

按以下顺序运行验证（每步必须通过才继续下一步）：

```
Lint → TypeCheck → Test → Build
```

对每个步骤，记录到 run.steps：

step 对象同样必须符合 `tools/schemas/verify.schema.json`。

如果某步骤的命令为 null（不可用），跳过该步骤。

### 5. 修复循环（TDD 纪律）

当验证失败时：

```
分析错误输出 → 定位失败原因 → 修改实现代码 → 重新验证 →
  ├─ 通过 → 继续下一步验证
  └─ 仍然失败 → 再次修复（最多 3 轮）→ 仍失败则报告
```

**修复时的禁止操作：**

| 禁止 | 原因 |
|------|------|
| 修改测试文件中的断言 | 违反 TDD：测试定义正确行为 |
| 添加 `.skip()` / `@pytest.mark.skip` | 逃避验证，不是修复 |
| 删除失败的测试用例 | 降低覆盖率，隐藏问题 |
| 放宽正则/匹配条件 | 变相修改预期行为 |
| 修改 lint 规则配置以消除警告 | 治标不治本 |
| 在 `tsconfig.json` 中跳过类型检查 | 隐藏类型错误 |

### 6. 完成验证运行

更新 verify.json 中的 run 记录，字段与取值范围继续以 `tools/schemas/verify.schema.json` 为准。

### 7. 更新关联状态（如果在工作流中）

如果 `.workflow/` 存在：

**scope = milestone 时**：
- 更新 `milestones.json` 对应里程碑的 `verify_result_summary`
- 追加事件到 `events.jsonl`

**scope = final 时**：
- 更新 `workflow.json.final_verify_overall` 为 `pass` 或 `fail`
- 如果 pass 且所有里程碑已完成，将 `workflow.json.phase` 推进为 `completed`
- 追加事件到 `events.jsonl`

### 8. 输出验证报告

```
## 验证报告 - {日期时间}

| 步骤 | 状态 | 详情 |
|------|------|------|
| Lint | ✅/❌ | {通过/N 个问题} |
| TypeCheck | ✅/❌ | {通过/N 个错误} |
| Test | ✅/❌ | {N 通过, N 失败, N 跳过} |
| Build | ✅/❌ | {通过/失败原因} |

### 修复记录
- {修改了什么文件，为什么}

### 未解决问题
- {仍然失败的项目及原因}
```

## 独立调用模式

此技能可以在没有 `.workflow/` 的情况下独立运行：
- 直接从项目配置检测验证命令
- 运行验证和修复循环
- 在终端输出报告（不写入 JSON 文件）

## 重要约束

- **TDD 铁律不可违反**：这是整个工作流的核心纪律
- **修复轮次有限**：单个失败项最多修复 3 轮，超出则报告人工介入
- **不跳过任何步骤**：即使某步"看起来"没问题，也要实际运行
- **验证结果写入 verify.json**：不依赖自由文本记录
- **final_verify_overall 是完成门禁**：不为 pass 时 workflow 不能进入 completed
