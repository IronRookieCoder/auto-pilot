---
name: plan
description: 基于 spec.md 生成 TDD 驱动的里程碑实施计划。当用户说"生成计划""制定计划""plan""拆分任务""规划里程碑"时使用此技能。分析规格说明，拆分为里程碑，输出到 milestones.json，投影生成 plan.md 供人工审阅。
version: 2.1.1
---

# 生成 TDD 驱动的里程碑计划

读取 `.workflow/spec.md`，将项目需求拆分为 TDD 驱动的里程碑序列，写入 `.workflow/milestones.json`，投影生成 `.workflow/plan.md` 供人工审阅。

## 前置检查

1. 确认 `.workflow/spec.md` 存在且内容已填充（不是空模板）
2. 确认 `.workflow/workflow.json` 存在
3. 检查 `workflow.json.status` 字段：
   - 如果为 `blocked`/`failed`/`paused`，向用户展示 `reason`，等待用户决策后再继续
4. 检查 `workflow.json.spec_approved` 是否为 `true`
   - 如果不是，提示用户先确认 spec：`python tools/workflow_confirm.py spec`
5. 如果 `.workflow/milestones.json` 已有里程碑，提示用户是否覆盖
6. 读取 `workflow.json.verify_commands` 了解项目验证能力

## 核心理念：TDD 驱动的里程碑

### 计划阶段的 TDD 职责

plan 阶段是 TDD 的 **设计阶段**，为 execute 阶段的 RED-GREEN 循环做好充分准备：

```
plan 阶段：定义验收标准 → 设计测试用例 → 明确实现范围 → 规划 RED 验证点
                                  ↓
execute 阶段：写测试 → 运行(RED) → 写实现 → 运行(GREEN) → 过 gate
```

**plan 阶段的 test_design 质量直接决定 execute 阶段能否顺利执行 TDD。** 如果 test_design 含糊不清，execute 阶段的子代理将无法写出有效的测试，导致 RED 阶段失败或被跳过。

### 什么是好的里程碑

里程碑不是"功能列表"，而是"可验证的交付单元"。每个里程碑必须同时满足：

1. **可测试**：有明确的 test_design，子代理能据此直接编写测试代码
2. **可验红**：测试在实现代码之前运行必须失败（RED），证明测试有效
3. **可验绿**：实现代码完成后测试通过（GREEN），证明功能正确
4. **可独立验证**：不依赖后续里程碑即可验证通过

## 执行步骤

### 1. 分析规格说明

读取 `.workflow/spec.md`，提取：
- 功能需求列表（每条必须有 `[FR-N]` 追踪 ID）
- 非功能需求
- 技术约束
- 验收标准（每条必须有 `[AC-N]` 追踪 ID）
- 范围边界（在范围内用 `[IN-N]`，不在范围内用 `[OUT-N]`）

如果 `spec.md` 中缺少追踪 ID，**先补齐 ID 再继续**（不修改 spec 的语义内容，仅添加 ID 标记）。

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

**TDD 导向的拆分策略：**
- 优先拆分出可被单元测试覆盖的模块，避免大量集成逻辑集中在一个里程碑
- 如果一个功能的测试需要复杂的 mock/stub 环境，考虑将环境搭建独立为前置里程碑
- 每个里程碑的 scope 应足够小，使测试和实现都能在单次上下文中完成

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

每个里程碑对象必须满足 `tools/schemas/milestones.schema.json`。字段名以 schema 为准，不在技能文档里重复维护完整 JSON 结构。

规划阶段至少要填充这些设计字段：
- `id`
- `title`
- `status`
- `dependencies`
- `acceptance_criteria`
- `test_design` — **TDD 核心字段，见下方质量标准**
- `tdd_type` — **必填**，见下方说明
- `test_files` — `tdd_type=standard` 时必填
- `scope`
- `key_files`
- `verify_commands`
- `spec_refs` — **必填**，见下方说明

#### tdd_type 字段说明

`tdd_type` 决定里程碑的 TDD 执行策略和门禁要求，**必须在规划阶段指定**：

| 值 | 含义 | RED 证据 | test_files |
|---|---|---|---|
| `standard` | 标准 TDD（写测试 → RED → 实现 → GREEN） | **必需** | **必填** |
| `setup` | 环境搭建（安装依赖、配置工具链） | 可选 | 可选 |
| `verification_only` | 仅验证（集成测试、端到端检查） | 可选 | 可选 |

**选择建议：**
- 大多数功能里程碑使用 `standard`
- M0（测试基础设施搭建）使用 `setup`
- 纯集成验证或文档类里程碑使用 `verification_only`

#### test_files 字段说明

`test_files` 列出该里程碑要创建或修改的测试文件路径。`tdd_type=standard` 时必须非空，用于：
- 子代理明确知道测试文件写在哪里
- gate 门禁验证测试文件是否确实存在
- lint 检查测试文件与 tdd_type 的一致性

#### spec_refs 字段说明

`spec_refs` 列出该里程碑覆盖的 `spec.md` 条目 ID。**每个里程碑必须至少引用一个 spec 条目**，用于：
- 证明每个里程碑与规格说明对齐
- lint 自动检查覆盖完整性和越界引用
- 人工审阅时直接看到"每个里程碑对应哪些规格条目"

**引用规则：**
- 可引用 `FR-*`（功能需求）、`AC-*`（验收标准）、`IN-*`（范围内条目）
- **不允许**引用 `OUT-*`（范围外条目）
- 所有引用的 ID 必须在 `spec.md` 中真实存在
- 所有 `FR-*`、`AC-*`、`IN-*` 条目必须被至少一个里程碑覆盖

**示例：**
```json
{
  "id": "M1",
  "title": "任务模型与创建接口",
  "spec_refs": ["FR-1", "IN-1", "AC-1"]
}
```

#### test_design 质量标准

test_design 是 execute 阶段子代理编写测试的 **唯一依据**。必须达到以下标准：

**必须包含：**
- 要测试的具体行为或功能点（不是抽象描述）
- 测试的输入和预期输出（或预期行为）
- 关键边界条件和异常场景

**合格示例：**
```
- 测试 parseConfig() 传入合法 JSON 返回配置对象
- 测试 parseConfig() 传入空字符串抛出 ConfigError
- 测试 parseConfig() 传入缺少必填字段的 JSON 返回含默认值的对象
```

**不合格示例（过于笼统，子代理无法据此写测试）：**
```
- 测试配置解析功能
- 确保错误处理正常
- 验证边界情况
```

**自检规则**：对每条 test_design，问"子代理能否仅凭此描述直接写出测试代码？"——如果不能，则需要细化。

### 6. 写入 milestones.json

将所有里程碑写入 `.workflow/milestones.json`，根结构和字段命名必须符合 `tools/schemas/milestones.schema.json`。如果已有 milestones.json，递增 revision。

如果写入失败，停止推进，检查原因后重试。

### 7. 投影生成 plan.md

**必须实际执行** `python tools/plan_sync.py export`：
- 从 `milestones.json` 生成 `plan.md`
- 在 `plan.md` 顶部写入 `<!-- milestones_revision: N -->`
- 已完成里程碑折叠为单行摘要
- 当前及待办里程碑保留完整格式
- 如果命令失败，停止推进状态，先修复同步问题

### 8. 更新 workflow.json

更新 `.workflow/workflow.json`，字段与取值范围以 `tools/schemas/workflow.schema.json` 为准。此步至少要保证：
- `phase = planning`
- `status = running`
- `updated_at` 为合法 ISO 8601 时间

如果更新失败，停止推进，检查原因后重试。

### 9. 追加事件

向 `events.jsonl` 追加一条符合 `tools/schemas/event.schema.json` 的 `plan_generated` 事件。

如果追加失败，停止推进，检查原因后重试。

### 10. 输出摘要

向用户展示：
1. 里程碑列表概览（编号 + 名称 + 依赖关系）
2. 依赖关系图
3. TDD 就绪度摘要（每个里程碑的 test_design 条目数 + verify_commands 配置情况）
4. 风险摘要
5. **人工审阅提醒**（必须醒目展示）：

```
+--------------------------------------------------------------+
|  计划已生成，等待人工审阅                                      |
|                                                              |
|  请打开 .workflow/plan.md 重点审阅以下内容：                    |
|                                                              |
|  [ ] 里程碑拆分粒度是否合理？                                  |
|  [ ] 每个里程碑的 test_design 是否具体到可直接写测试？           |
|  [ ] acceptance_criteria 是否可量化验证？                       |
|  [ ] 依赖关系是否正确？有无循环依赖？                           |
|  [ ] verify_commands 是否具体可执行？                           |
|  [ ] M0（测试基础设施）是否充分？                               |
|                                                              |
|  确认后运行：                                                  |
|    python tools/workflow_confirm.py plan                      |
|  或通过 /auto-pilot:run 继续                                   |
|                                                              |
|  [!] plan 未经确认不能进入执行阶段                              |
|  [!] test_design 质量直接影响 TDD 执行效果                      |
+--------------------------------------------------------------+
```

### 最后一步：工作流一致性校验

**必须实际执行**：

```bash
python -X utf8 tools/workflow_lint.py --workflow-dir .workflow
```

如果 lint 报告任何错误，**本技能视为未完成**，根据错误信息修正 `.workflow/` 文件后，重新执行 lint 直至零错误。

如果 lint 输出 warning（例如 `test_design` 少于 2 条），可以继续推进，但必须在输出摘要里明确提醒用户审阅这些风险。

## 重要约束

- **测试设计是必需项**：每个里程碑必须包含 test_design，没有测试的里程碑不合格
- **test_design 必须可操作**：子代理必须能仅凭 test_design 编写出有效的测试代码，不能只是抽象描述
- **RED 阶段必须可行**：test_design 描述的测试在实现前运行必须失败；如果测试不可能先失败（如纯配置类任务），在 test_design 中注明原因并设计替代验证方式
- **不修改 spec.md**：发现规格问题时在输出中提示用户，不自行修改
- **里程碑粒度适中**：太大难以验证，太小浪费开销，单个里程碑的实现时间应在 15-60 分钟
- **验证命令必须具体**：不能写"运行测试"，要写具体命令（如 `npm test -- --testPathPattern=config`）

- **spec_approved 是前置条件**：spec 未确认不能生成计划
- **spec_refs 是必填字段**：每个里程碑必须通过 spec_refs 证明与 spec.md 对齐；所有 FR-*/AC-*/IN-* 条目必须被覆盖
- **milestones.json 是真相源**：plan.md 是投影视图，不是独立真相源
- **plan_approved 由用户触发**：plan 不能自行将 plan_approved 置为 true
- **审阅是强制门禁**：输出摘要必须包含完整的审阅提醒，不能省略或简化
