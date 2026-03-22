# 编排者手册

> execute 主技能只负责编排，不直接承担里程碑内的编码实现。

## 编排职责

1. 读取 `.workflow/workflow.json`、`.workflow/milestones.json`、`.workflow/spec.md`
2. 选择下一个依赖已满足的 `pending` 里程碑
3. 将里程碑标记为 `in_progress`，并更新 `workflow.json.current_milestone_id`
4. 追加 `milestone_started` 事件到 `events.jsonl`
5. 生成子代理并下发里程碑契约
6. 接收子代理结果并写入 `verify.json`、`milestones.json`、`events.jsonl`
7. 实际执行 `python tools/workflow_gate.py milestone <id>`
8. gate 通过后，实际执行 `python tools/plan_sync.py export`
9. 选择下一个里程碑或将工作流推进到 `verifying`

## 失败处理

- 子代理返回 `failed` 或 `blocked`：停止推进，更新 `workflow.json.status`
- gate 失败：里程碑不得标记为 `completed`
- `plan_sync.py export` 失败：停止推进状态，先修复投影问题

## 编排边界

- 不在编排层直接写实现代码
- 不在编排层绕过 `workflow_gate.py`
- 不手写 `plan.md`
- 不让子代理直接改 `.workflow/` 状态文件
