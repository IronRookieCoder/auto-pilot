# 验证策略

> 本文件定义验证执行的标准流程。

## 验证序列

每个里程碑完成后，必须按以下顺序运行验证：

```
Lint → TypeCheck → Test → Build
```

每步必须通过才继续下一步。

## 验证命令来源

按优先级从以下来源获取验证命令：

1. `milestones.json` 中当前里程碑的 `verify_commands`（局部优先）
2. `workflow.json` 中的全局 `verify_commands`
3. 如果以上都没有，从项目配置文件自动检测

## 自动检测规则

| 项目类型 | Lint | TypeCheck | Test | Build |
|----------|------|-----------|------|-------|
| Node/npm | `npm run lint` | `npx tsc --noEmit` | `npm test` | `npm run build` |
| Python | `ruff check .` | `mypy .` | `pytest` | - |
| Go | `golangci-lint run` | （编译即检查） | `go test ./...` | `go build ./...` |
| Rust | `cargo clippy` | （编译即检查） | `cargo test` | `cargo build` |

## 验证结果记录

每次验证必须写入 `verify.json`，包含：

- 验证运行 ID
- 每个步骤的命令、退出码、开始/结束时间、输出摘要
- 总体结果（pass/fail）
- 关联的里程碑 ID 或 "final"

## 验证失败处理

- 分析错误 → 修改实现代码 → 重新验证
- 单个步骤最多 3 轮修复
- 3 轮后仍失败：返回"阻塞"状态
- 里程碑的 `verify_result_summary` 更新为失败摘要
