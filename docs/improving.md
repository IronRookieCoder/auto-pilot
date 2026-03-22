## 框架根本性限制

以上问题可以归并为三个系统性根因：

### R1. 纯指令驱动，无确定性门禁

| SKILL.md 中的设计 | 实际结果 |
|---|---|
| TDD 循环“严格执行” | 可被跳过 |
| 里程碑“必须折叠” | 可不发生 |
| 验证命令“必须执行” | 可缺失、可不运行 |
| 禁止事项 6 条 | 仅是文本约束 |

当前约束主要是“语义约束”，依赖 LLM 理解并自愿遵守，没有程序化校验。

### R2. 状态与信息传递链脆弱

当前状态散落在多个 Markdown 文件中，阶段推进依赖 LLM 解析模板、标题和标记。任一文件结构漂移，都会影响后续执行、恢复和验证。

另一个关键问题是：`init` 目前把验证命令标记为“非必需”。这会让“初始化 -> 计划 -> 执行 -> 验证”整条链路在缺少验证命令时继续运行，直到最后才暴露失败，甚至根本不暴露。

### R3. 指令复杂度上升后，LLM 遵循度衰减

随着规则、模板、例外情况越来越多，LLM 更容易“压缩执行”或“挑重点执行”。这不是再补几段提示词就能解决的问题。必须把关键正确性条件移出 prompt，交给脚本和结构化状态检查。

---

## 修复原则

设计原则：**人审内容保留 Markdown，机器状态全部结构化**。

- Markdown 只承担“人类输入”和“人工审阅”职责。
- JSON/JSONL 承担状态、验证结果、事件记录的真相源职责。
- 脚本负责校验和门禁，提示词只负责引导 LLM 配合这些机制。

## 目标架构

### 一、保留的 Markdown

#### 1. `spec.md`

作用：唯一必须保留的人工审阅文件。

适合保留为 Markdown 的原因：

- 需求、边界、验收标准本来就是面向人的内容
- 用户需要直接阅读、修改、确认
- 这部分不适合强行结构化到 JSON 作为主要编辑载体

#### 2. `plan.md`

作用：里程碑拆分的人工审阅与确认文件。

设计建议：

- 必须保留
- 必须经过人工校验后，工作流才能从 `planning` 进入 `executing`
- 不再是执行真相源，但必须是机器真相源的人工确认投影视图
- 允许由 `milestones.json` 投影生成，再由人工审阅确认
- 人工修改后，必须回写并通过结构校验，再更新 `milestones.json`

#### `plan.md <-> milestones.json` 同步机制

必须定义唯一同步机制，避免 `plan.md` 再次演化成第二真相源。

##### 同步原则

- `milestones.json` 是里程碑结构与状态的唯一执行真相源
- `plan.md` 是它的人工审阅投影视图
- 人可以修改 `plan.md`
- 但 `plan.md` 的修改不能直接视为已生效，必须经过“解析 -> 校验 -> 回写”流程

##### 唯一写回路径

- 只允许通过固定脚本将 `plan.md` 回写到 `milestones.json`
- 不允许 agent 或用户手工同时修改两个文件后再让系统猜测谁是最新
- `plan_sync export` 时必须在 `plan.md` 中写入当前 `milestones_revision`
- `plan_sync import` 时必须校验 `plan.md` 中的 `milestones_revision` 与当前 `milestones.json.revision` 一致

建议入口：

- `python tools/plan_sync.py export`
  - 从 `milestones.json` 生成 `plan.md`
- `python tools/plan_sync.py import`
  - 解析 `plan.md`
  - 校验结构
  - 回写 `milestones.json`

##### 冲突处理

- 默认真相源优先级：
  - 执行中：`milestones.json` 优先
  - 计划审阅阶段：允许 `plan.md` 通过 import 覆盖 `milestones.json`
- 如果出现以下任一情况，直接判定为冲突：
  - `plan.md` 中的 `milestones_revision` 与当前 `milestones.json.revision` 不一致
  - `plan.md` 缺失 revision/checksum 元数据
  - `plan.md` 的结构化内容解析成功，但 checksum 校验失败
  - 直接报冲突
  - 不自动合并
  - 不进入 `executing`

##### 失败处理

- `plan_sync import` 失败时：
  - `plan_approved` 必须保持 `false`
  - `workflow.phase` 保持在 `planning`
  - 输出具体失败原因

##### 建议限制

- `plan.md` 只允许编辑：
  - 里程碑标题
  - 依赖关系
  - 验收标准
  - 测试设计
  - 范围说明
- 不允许在 `plan.md` 中直接编辑：
  - 里程碑运行状态
  - RED/GREEN 证据
  - verify 结果
  - 完成时间

### 二、改为机器真相源的文件

#### 1. `workflow.json`

作用：工作流总状态真相源。

建议记录：

- `phase`
- `status`
- `reason`
- `current_milestone_id`
- `spec_approved`
- `plan_approved`
- `verify_commands`
- `final_verify_overall`
- `updated_at`

其中：

`phase` 只表示流程阶段，单向流转：
- `init`
- `planning`
- `executing`
- `verifying`
- `completed`

`status` 表示当前运行态：
- `running`
- `blocked`
- `paused`
- `failed`

并要求：

- `planning -> executing` 的前置条件是 `plan_approved == true`
- `init -> planning` 的前置条件是 `spec_approved == true`
- `completed` 只能作为 `phase` 进入条件，不能作为 `status`
- `blocked/paused/failed` 只能属于 `status`
- `blocked/paused/failed` 时必须记录 `reason`

#### 2. `milestones.json`

作用：所有里程碑的结构化定义与执行状态真相源。

建议记录每个里程碑：

- `id`
- `title`
- `status`
- `revision`
- `dependencies`
- `acceptance_criteria`
- `test_design`
- `scope`
- `key_files`
- `verify_commands`
- `red_evidence`
- `test_result`
- `verify_result_summary`
- `decision_log`
- `completed_at`

说明：

- 当前 `plan.md` 中的大部分“执行性内容”都应迁到这里
- `execute` 不再解析 Markdown 标题和 emoji，而是直接读取这里

#### 3. `verify.json`

作用：验证结果真相源。

建议记录：

- `revision`
- 每次 lint/typecheck/test/build 的命令
- 退出码
- 开始与结束时间
- 摘要
- 关联的 milestone 或 final verify
- `checksum`

说明：

- 不再把“测试通过了”只写成一段自由文本
- 后续门禁脚本从这里读结果，不信任子代理自报

#### 4. `events.jsonl`

作用：事件流真相源，替代自由文本历史记录。

建议每条事件记录：

- `time`
- `type`
- `phase`
- `milestone_id`
- `summary`
- `artifacts`

说明：

- JSONL 适合追加写
- 比 Markdown 更容易做审计、回放、恢复和汇总

### 三、字段归属与确认权限

必须显式定义字段归属，避免多个 JSON 文件重复持有同一事实。

#### 字段归属表

| 字段/信息 | 唯一 owner | 允许派生/引用 | 说明 |
|---|---|---|---|
| `phase` | `workflow.json` | 其他文件可读不可写 | 工作流总阶段 |
| `status`（工作流级） | `workflow.json` | 其他文件可读不可写 | 如 blocked/paused/failed |
| `reason`（工作流级） | `workflow.json` | 可在 `events.jsonl` 留痕 | 阶段阻塞/失败原因 |
| `current_milestone_id` | `workflow.json` | `milestones.json` 可被引用 | 当前执行游标 |
| `spec_approved` | `workflow.json` | 不允许其他文件持有同义字段 | 人工确认门禁 |
| `plan_approved` | `workflow.json` | 不允许其他文件持有同义字段 | 人工确认门禁 |
| 里程碑结构定义 | `milestones.json` | `plan.md` 为投影 | 标题/依赖/验收标准等 |
| 里程碑运行状态 | `milestones.json` | `workflow.json` 只引用当前 id | 不写回 `plan.md` |
| 里程碑级 `verify_commands` | `milestones.json` | `workflow.json` 可持全局默认命令 | 局部优先于全局 |
| 全局 `verify_commands` | `workflow.json` | `milestones.json` 可继承 | 默认验证命令 |
| 里程碑级详细验证结果 | `verify.json` | `milestones.json` 仅缓存 `verify_result_summary` | 详细结果只保留一处 |
| `verify_result_summary` | `milestones.json` | 可从 `verify.json` 派生 | 只保留摘要 |
| 最终详细验证结果 | `verify.json` | `workflow.json` 只保留 `final_verify_overall` | 避免双写完整结果 |
| 事件流 | `events.jsonl` | 其他文件只能汇总 | 追加式历史事实 |
| `decision_log` | `milestones.json` | 可由 `events.jsonl` 汇总生成 | 只保留里程碑摘要，不保存完整历史 |

#### 归属规则

- 任何字段只能有一个真相源 owner
- 其他文件若需要使用：
  - 要么引用
  - 要么缓存摘要
  - 不能再保存一份可独立修改的完整版

#### 确认字段权限边界

`spec_approved` 和 `plan_approved` 必须是强门禁字段，不能由 agent 自行置位。

##### 允许写入者

- `spec_approved`
  - 只能由显式用户确认动作触发
- `plan_approved`
  - 只能由显式用户确认动作触发

##### 不允许的行为

- agent 不能因为“用户大概率会同意”就自动置 `spec_approved = true`
- agent 不能因为 `plan.md` 看起来合理就自动置 `plan_approved = true`
- lint/gate 脚本只能校验确认状态，不能替代用户确认

##### 建议落地方式

- 将确认动作单独记录为事件：
  - `events.jsonl` 追加 `spec_approved` 事件
  - `events.jsonl` 追加 `plan_approved` 事件
- 再由确认入口脚本更新 `workflow.json`

建议入口：

- `python tools/workflow_confirm.py spec`
- `python tools/workflow_confirm.py plan`

##### 阶段门禁

- `spec_approved != true`
  - 不能从 `init` 进入 `planning`
- `plan_approved != true`
  - 不能从 `planning` 进入 `executing`

## 新的 `.workflow/` 建议结构

### 最小化版本

```text
.workflow/
├── spec.md              # 人工审阅真相源
├── plan.md              # 人工校验后的计划文件
├── workflow.json        # 工作流状态真相源
├── milestones.json      # 里程碑真相源
├── verify.json          # 验证结果真相源
└── events.jsonl         # 事件流真相源
```

---

## 修复措施

### F01 | 收缩 Markdown：人工文件只保留 `spec.md` 和 `plan.md`

**对应根因**：R2、R3

调整原则：

- `spec.md` 保留，作为需求与边界确认文件
- `plan.md` 保留，作为里程碑计划人工校验文件
- `plan.md` 不是执行真相源，但它是进入执行阶段的必需门禁材料
- 删除 `documentation.md`、`changelog.md`、`implement.md`

这一步会直接消除“多个 Markdown 互相打架”的大部分问题。

#### `implement.md` 删除后的规则归属

`implement.md` 承载的关键内容不能消失，只能迁移。

迁移原则：

- 项目状态与执行结果：进入 `.workflow/*.json`
- 全局执行规则与固定约束：迁移到插件仓库内的 `skills/execute/references/`

建议迁移内容：

- TDD 铁律
- 禁止事项清单
- execute 编排规则
- 子代理固定执行契约
- 通用验证纪律

建议文件：

```text
skills/
└── execute/
    ├── SKILL.md
    └── references/
        ├── execution-rules.md
        ├── tdd-guardrails.md
        └── validation-policy.md
```

使用方式：

- `execute/SKILL.md` 不再要求读取项目内 `implement.md`
- `execute/SKILL.md` 改为显式加载 `skills/execute/references/*.md`
- 项目特定验证命令不放在 references 中，而放在：
  - `workflow.json.verify_commands`
  - `milestones.json[*].verify_commands`

这样可以把“插件级固定规则”和“项目级可变状态”彻底分层。

### F02 | 引入 `workflow.json` + `milestones.json` 作为执行真相源

**对应根因**：R1、R2

执行、恢复、门禁全部基于结构化状态：

- `run` 读 `workflow.json`
- `execute` 读 `milestones.json`
- `verify` 写 `verify.json`
- `status` 从这些 JSON 汇总

但进入执行阶段前，必须满足：

- `spec_approved == true`
- `plan_approved == true`

这一步之后，任何阶段都不应再依赖解析 Markdown 标题和 emoji。

### F03 | 引入 `verify.json` + `events.jsonl`

**对应根因**：R1

把“验证通过”“发生过什么”从自由文本里抽出来：

- `verify.json` 负责保存可机器核验的验证结果
- `events.jsonl` 负责保存可追加、可追溯的事件流

这一步之后：

- `final_verify_overall != pass` 时，不允许 workflow 完成

### F04 | 引入 `workflow-lint` 和 `workflow-gate`

**对应根因**：R1

建议统一入口，不要写死 `bash .workflow/...`：

- `python tools/workflow_lint.py <phase>`
- `python tools/workflow_gate.py milestone <id>`

或对应的 Node 版本。

职责区分：

- `workflow-lint`
  - schema 校验
  - phase 前置条件校验
  - 派生 Markdown 与 JSON 一致性校验
- `workflow-gate`
  - 里程碑是否允许完成
  - 是否存在 RED 证据
  - 是否有测试工件变化
  - 是否有实际验证结果

### F05 | `init` 改成“探测能力 + 标记缺失”

**对应根因**：R2

`init` 应负责：

- 探测项目类型
- 尽量填入 `verify_commands`
- 对缺失项显式写入 `workflow.json`

如果缺失测试能力：

- 允许初始化成功
- 但 `plan` 必须生成 `M0: 测试基础设施`
- `execute` 只能先执行 M0

说明：

- 原 `implement.md` 中的“验证命令表”不再作为项目内 Markdown 存在
- 项目级验证命令改由结构化字段承载
- execute 子代理的固定纪律从 `skills/execute/references/` 读取

### F06 | Markdown 改为“人工确认文件”，不再承担状态机职责

**对应根因**：R2、R3

这条很关键：

- 人可以读 Markdown
- 人必须审阅 `spec.md` 和 `plan.md`
- 但流程推进不能依赖 Markdown 是否“看起来像完成”

只要 JSON 与 Markdown 不一致，就以 JSON 为准，并由 lint 报错。

---

## 各层协作关系

```text
人工审阅层                     机器真相层
┌──────────────────────┐      ┌──────────────────────────┐
│ spec.md              │      │ workflow.json            │
│   需求与边界         │      │   phase / approvals      │
│ plan.md              │      │ milestones.json          │
│   计划人工校验       │      │   里程碑结构与状态       │
└──────────┬───────────┘      │ verify.json             │
           │                  │   验证结果               │
           │                  │ events.jsonl            │
           │                  │   事件流                 │
           │                  └──────────┬───────────────┘
           │                             │
           └──── 脚本生成/对账视图 ───────┘

             workflow-lint / workflow-gate
             负责门禁、恢复、完成判断
```

---

## 落地顺序

1. 先定义 `workflow.json`、`milestones.json`、`verify.json` schema
2. 再实现 `workflow-lint` 和 `workflow-gate`
3. 调整 `init`
   - 生成结构化文件
   - 生成 `spec.md`
4. 调整 `plan`
   - 输出到 `milestones.json`
   - 强制投影生成 `plan.md`
   - 等待人工校验后再将 `plan_approved` 置为 `true`
5. 调整 `execute`
   - 只读 `milestones.json`
   - 前置条件必须包含 `plan_approved == true`
   - 完成前必须过 gate
6. 调整 `verify`
   - 写 `verify.json`
7. 删除旧的 `documentation.md`、`changelog.md`、`implement.md` 相关逻辑与模板
8. 在插件侧新增 `skills/execute/references/`，承接原 `implement.md` 的固定规则

---

## 验收标准

### A1. 人审文件收敛且明确

- 必需 Markdown 只保留 `spec.md` 和 `plan.md`
- 其他 Markdown 文件从设计中移除

### A2. 状态不再依赖 Markdown

- `run/execute/verify/status` 不再解析 Markdown 标题和 emoji
- 恢复执行只依赖 JSON 真相源

### A3. 不再跳过计划审阅直接执行

- `plan_approved != true` 时，workflow 不能从 `planning` 进入 `executing`

### A4. 不再出现“文档看起来完成，但状态机不认可”

- JSON 与 Markdown 不一致时，lint 失败并停止

### A5. 不再出现“verify 被跳过仍完成”

- `final_verify_overall != pass` 时，workflow 不能进入 `completed`

### A6. 合法支持“先补测试基础设施”

- 对没有现成测试命令的项目，workflow 仍可初始化
- 但必须先完成 `M0: 测试基础设施` 才能继续后续里程碑
