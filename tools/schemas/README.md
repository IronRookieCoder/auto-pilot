# Schema Authority

`tools/schemas/*.json` 是 Auto-Pilot 结构化状态的唯一权威定义。

## Canonical Files

- `workflow.schema.json`
- `milestones.schema.json`
- `verify.schema.json`
- `event.schema.json`

## Usage Rule

- README 只描述职责，不重复维护完整字段清单。
- SKILL 文档只描述流程和门禁，字段名与结构以 schema 为准。
- 初始化 `.workflow/` 时，JSON 文件必须直接对齐这些 schema。
- `plan.md` 的骨架不手写，必须通过 `python tools/plan_sync.py export` 从 `milestones.json` 投影生成。

## Related Validators

- `python tools/workflow_lint.py`
- `python tools/workflow_gate.py`
- `python tools/plan_sync.py`
