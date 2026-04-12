# Changelog

所有重要变更按版本记录。格式基于 [Keep a Changelog](https://keepachangelog.com/)。

---

## v3.4.1 — 2026-04-12

> 修复 hooks.json 结构以适配 Claude Code v2.1.x，修正文档中的安装方式和无效事件类型引用。

### 修复

- **hooks/hooks.json** — 适配 Claude Code v2.1.x hooks 结构
  - `PreToolUse` 条目补充 `hooks` 嵌套数组（v2.1.x 要求 `matcher` + `hooks[]` 结构）
  - `PostSkill` 改为 `PostToolUse`（`PostSkill` 不是合法的 hook 事件类型），使用 `matcher: "Skill"` 匹配技能调用
- **README.md** — 安装说明更新
  - 改为在线安装方式 `claude plugin add https://github.com/IronRookieCoder/auto-pilot`
  - Protection Hooks 部分 `PostSkill` 更正为 `PostToolUse`
- **README_CN.md** — 同步中文文档的安装说明和保护钩子描述

---

## v3.4.0 — 2026-03-25

> 引入 spec-plan 一致性硬门禁：spec.md 追踪 ID + milestones.json spec_refs + lint 自动校验。

### 新增

- **tools/schemas/milestones.schema.json** — 新增 `spec_refs` 字段
  - 字符串数组，元素格式为 `FR-N`/`AC-N`/`IN-N`，不允许 `OUT-*`
- **tools/workflow_lint.py** — `check_spec_plan_consistency()` spec-plan 一致性检查
  - 解析 `spec.md` 中的追踪 ID（`FR-*`/`AC-*`/`IN-*`/`OUT-*`）
  - 每个里程碑必须有 `spec_refs`，否则报错
  - 引用 `OUT-*` 条目报错
  - 引用不存在的 spec 条目报错
  - `FR-*`/`AC-*`/`IN-*` 全部必须被至少一个里程碑覆盖
  - 单个里程碑引用过多条目时警告
  - AC 映射过度集中时警告
- **tools/workflow_lint.py** — `validate_milestones()` 新增 `spec_refs` 类型和格式校验
- **tools/plan_sync.py** — spec_refs 导入导出支持
  - `export`: 从 `milestones.json` 投影出「规格映射」展示块
  - `import`: 将 `plan.md` 中的规格映射回写到 `milestones.json`
  - `PRESERVED_FIELDS` 新增 `spec_refs`
- **skills/init/references/spec-template.md** — 模板增加追踪 ID 格式
  - 功能需求使用 `[FR-N]`，验收标准使用 `[AC-N]`
  - 范围内使用 `[IN-N]`，范围外使用 `[OUT-N]`
- **tests/test_spec_plan_consistency.py** — 新增 17 个测试用例
  - 覆盖完整覆盖、缺失 spec_refs、引用不存在 ID、引用 OUT-*、AC/IN/FR 未覆盖、无追踪 ID、过多引用、AC 集中等场景

### 增强

- **skills/plan/SKILL.md** — 新增 `spec_refs` 字段说明和引用规则
  - 分析规格说明步骤增加追踪 ID 要求
  - 重要约束增加 spec_refs 必填规则
- **README.md** — 补充 spec-plan 一致性追踪说明

### 版本

- **.claude-plugin/plugin.json** — 版本更新到 `3.4.0`
- **.claude-plugin/marketplace.json** — marketplace 元数据版本更新到 `3.4.0`

---

## v3.3.1 — 2026-03-25

> 收紧 executing 恢复门禁，彻底阻止绕过非当前 failed 里程碑。

### 修复

- **tools/workflow_resume.py** — executing 恢复条件补强
  - `current_milestone_id` 为空但存在 `failed` 里程碑时，恢复直接失败
  - `current_milestone_id` 指向其他里程碑、但仍存在非当前 `failed` 里程碑时，恢复直接失败
- **skills/execute/SKILL.md** — 恢复顺序补充 failed 里程碑优先级说明
- **skills/execute/references/orchestrator-playbook.md** — 将"不存在当前 failed/in_progress"收紧为"不存在任何未处理的 failed/in_progress"
- **README.md** — 恢复语义补充 failed 里程碑不可绕过说明

### 测试

- **tests/test_workflow_resume.py** — 新增 2 个用例
  - `current_milestone_id=null` 且存在 failed 里程碑时应拒绝恢复
  - `current_milestone_id` 指向其他里程碑、但存在非当前 failed 里程碑时应拒绝恢复

### 版本

- **.claude-plugin/plugin.json** — 版本更新到 `3.3.1`
- **.claude-plugin/marketplace.json** — marketplace 元数据版本更新到 `3.3.1`

---

## v3.3.0 — 2026-03-25

> 为恢复流程补上脚本硬门禁，并收紧 failed 里程碑的恢复/跳过语义。

### 新增

- **tools/workflow_resume.py** — 工作流恢复门禁脚本
  - 只允许 `status=blocked/paused/failed` 的工作流恢复
  - 恢复前先执行 lint 与阶段一致性校验
  - 对 `executing` / `verifying` 阶段补充恢复前检查
  - 恢复成功后写入 `workflow_resumed` 事件并清除旧 `reason`
- **tests/test_workflow_resume.py** — 恢复门禁测试
  - 覆盖成功恢复、不可恢复状态、lint 失败、`verifying` 阶段未完成里程碑等场景

### 变更

- **skills/run/SKILL.md** — 恢复与收尾职责重写
  - 恢复流程改为必须调用 `workflow_resume.py`
  - failed 里程碑"跳过"改为只能先调整计划/依赖关系，禁止直接继续下一个 `pending`
  - `verify` / `completed` 的 phase 推进职责明确归属给子技能
- **skills/execute/SKILL.md** — 中断恢复策略收紧
  - 优先恢复 `current_milestone_id` 指向的失败或进行中里程碑
  - 明确 failed 里程碑不得直接越过
- **skills/execute/references/orchestrator-playbook.md** — 编排失败处理补充恢复门禁
- **skills/status/SKILL.md** — 状态摘要模板增加 `reason` 展示
- **README.md** — 新增 `workflow_resume.py` 用法与恢复规则说明

### 版本

- **.claude-plugin/plugin.json** — 版本更新到 `3.3.0`
- **.claude-plugin/marketplace.json** — marketplace 元数据版本更新到 `3.3.0`

---

## v3.2.1 — 2026-03-24

> 修复 plan 确认与 TDD 就绪度校验中的 4 个行为缺口。

### 修复

- **tools/workflow_lint.py** — H3 的 `test_design < 2` 改为 warning，不再导致 lint 失败
  - 新增 `lint_workflow_dir()`，统一返回 `errors` / `warnings`
  - CLI 保留 warning 输出，但退出码仅由 error 决定
- **tools/workflow_confirm.py** — `confirm_plan()` 在设置 `plan_approved=true` 前追加 lint 校验
  - `import_plan()` 成功后仍需通过 lint，防止无效计划进入 `executing`
  - warning 会提示，但不阻断确认
- **tools/plan_sync.py** — `import_plan()` 新增 `tdd_type` / `test_files` 导回
  - 新增里程碑经 `plan.md -> import` 回写后，不再丢失新字段
- **hooks/validate_workflow_write.py** — 首次创建 `workflow.json` 时也拦截 `approved=true`
  - 修复“新文件首写可绕过 approved 写保护”的漏洞

### 测试

- **tests/test_plan_sync.py** — 新增 `plan_sync import` 新字段回写测试
- **tests/test_workflow_confirm.py** — 新增 `confirm_plan()` 的 lint 门禁测试
- **tests/test_workflow_lint.py** — H3 调整为 warning 语义测试
- **tests/test_validate_workflow_write.py** — 首次创建文件的写保护测试更新

---

## v3.2.0 — 2026-03-24

> TDD 强化实施：堵硬缺口 + 新增 tdd_type/test_files 字段 + approved 写保护。

### 新增

- **tools/schemas/milestones.schema.json** — 新增 `tdd_type` 和 `test_files` 字段
  - `tdd_type`（enum: standard/setup/verification_only）加入 required，决定 TDD 执行策略
  - `test_files`（string array）列出里程碑的测试文件路径
- **tools/workflow_lint.py** — H1：`test_design`/`acceptance_criteria` 非空检查
  - 空数组时 lint 报错，防止"结构合法但 TDD 准备不足"的计划
- **tools/workflow_lint.py** — F1/F2：`tdd_type` enum 校验 + `test_files` 类型校验
  - `tdd_type=standard` 时强制 `test_files` 非空
  - `status=completed` 时根据 `tdd_type` 决定 `red_evidence` 是否必需（setup/verification_only 可选）
- **tools/workflow_lint.py** — H3：`check_plan_tdd_readiness()` TDD 就绪度检查
  - `test_design` 少于 2 条时警告
  - 无测试命令且无 M0 时报错
  - 在 `planning`/`executing` 阶段自动调用
- **hooks/validate_workflow_write.py** — H2：`approved` 字段写保护
  - `spec_approved`/`plan_approved` 从非 true 变为 true 时拦截
  - 仅允许 `workflow_confirm.py` 工具设置这些字段
- **tools/workflow_gate.py** — `tdd_type` 分支门禁
  - `standard`/默认：`red_evidence` 必需
  - `setup`/`verification_only`：`red_evidence` 可选
- **tools/plan_sync.py** — 新字段同步支持
  - `PRESERVED_FIELDS` 添加 `tdd_type`/`test_files`
  - `export_plan()` 渲染 TDD 类型和测试文件列表
- **tests/** — 新增 3 个测试文件（26 个测试用例）
  - `test_workflow_lint.py`：lint 校验逻辑测试
  - `test_workflow_gate.py`：gate tdd_type 分支测试
  - `test_validate_workflow_write.py`：approved 写保护测试

### 增强

- **skills/plan/SKILL.md** — 补充 `tdd_type`/`test_files` 字段说明和选择建议
- **skills/execute/SKILL.md** — 补充 tdd_type 分支执行策略和 test_files 使用方式
- **skills/execute/references/subagent-contract.md** — 输入上下文新增 `tdd_type` 和 `test_files`

---

## v3.1.0 — 2026-03-24

> 强化 plan 技能的 TDD 理念，确保 AI 遵循 TDD 流程并提醒用户审阅。

### 增强

- **skills/plan/SKILL.md** — 核心理念部分重写，明确 plan 阶段与 execute 阶段的 TDD 职责分工
  - 新增"计划阶段的 TDD 职责"章节，阐明 plan 阶段是 TDD 的设计阶段
  - 新增"什么是好的里程碑"章节，定义可测试、可验红、可验绿、可独立验证四项标准
- **skills/plan/SKILL.md** — 新增 TDD 导向的拆分策略
  - 优先拆分可被单元测试覆盖的模块
  - 复杂 mock/stub 环境独立为前置里程碑
  - 里程碑 scope 控制在单次上下文可完成范围
- **skills/plan/SKILL.md** — 新增 test_design 质量标准
  - 定义必须包含的内容：具体行为、输入/输出、边界条件
  - 提供合格/不合格示例对比
  - 新增自检规则："子代理能否仅凭此描述直接写出测试代码？"
- **skills/plan/SKILL.md** — 输出摘要增加 TDD 就绪度摘要和结构化审阅清单
  - 新增 TDD 就绪度摘要项（test_design 条目数 + verify_commands 配置情况）
  - 人工审阅提醒从简单文字升级为醒目的结构化清单框
  - 审阅清单包含 6 项 TDD 视角的检查点
- **skills/plan/SKILL.md** — 重要约束新增 3 条 TDD 相关规则
  - test_design 必须可操作（子代理可据此直接写测试）
  - RED 阶段必须可行（测试在实现前必须失败）
  - 审阅是强制门禁（输出摘要不能省略审阅提醒）

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
