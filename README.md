# Auto-Pilot：长周期 TDD 编码工作流插件

基于"持久化项目记忆 + TDD 驱动执行"的 Claude Code 插件，使 AI 编码代理能在长时间任务中保持连贯性和代码质量。

## 核心理念

通过 5 个 Markdown 文件构成代理的"外部大脑"，配合里程碑驱动的 TDD 执行循环：

```
.workflow/
├── spec.md            # 冻结目标 - 做什么、边界在哪
├── plan.md            # 执行蓝图 - 活跃里程碑（已完成的自动折叠）
├── implement.md       # 操作规程 - TDD 规则和验证命令
├── documentation.md   # 状态仪表盘 - 当前状态、活跃问题（≤100 行）
└── changelog.md       # 历史归档 - 完整执行日志（日常不读取）
```

**TDD 铁律贯穿全流程**：测试先行、禁止修改测试以通过验证。

**注意力保护机制**：已完成里程碑折叠为单行、documentation 控制在 100 行内、详细日志归档到 changelog，确保 AI 在长周期任务中聚焦当前工作。

## 技能列表

| 技能 | 命令 | 说明 |
|------|------|------|
| init | `/auto-pilot:init` | 初始化项目记忆，创建 .workflow/ 目录 |
| plan | `/auto-pilot:plan` | 基于 spec.md 生成 TDD 驱动的里程碑计划 |
| execute | `/auto-pilot:execute` | 逐里程碑 TDD 循环执行 |
| verify | `/auto-pilot:verify` | 质量验证（可独立调用） |
| status | `/auto-pilot:status` | 查看进度（可独立调用） |
| run | `/auto-pilot:run` | 一键全流程编排 |

## 使用方式

### 全自动（推荐）

```
/auto-pilot:run 实现一个 TODO 应用，支持增删改查和分类功能
```

自动走完 init → plan → execute → 完成。

### 分步式

```
/auto-pilot:init          # 1. 初始化
# 编辑 .workflow/spec.md   # 2. 完善需求
/auto-pilot:plan          # 3. 生成计划
# 审阅 .workflow/plan.md   # 4. 审阅计划
/auto-pilot:execute       # 5. 逐里程碑执行
```

### 独立调用

```
/auto-pilot:verify        # 随时检查质量
/auto-pilot:status        # 随时查看进度
```

## TDD 工作流

每个里程碑的执行循环：

```
定义测试 → 确认 RED → 编写实现 → 验证 GREEN → 标记完成
    ↑                                    |
    └─── 失败时只改实现，禁止改测试 ←────┘
```

## 中断恢复

工作流支持在任何时刻中断。重新调用 `/auto-pilot:run` 或 `/auto-pilot:execute` 时，自动从断点继续。

## 安装

将 `auto-pilot` 目录放置在 Claude Code 可以识别的插件路径下，或使用：

```bash
claude --plugin-dir ./auto-pilot
```
