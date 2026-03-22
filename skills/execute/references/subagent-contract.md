# 子代理契约

> 每个里程碑子代理都必须按此契约执行并返回结构化结果。

## 输入上下文

- 里程碑 ID 与标题
- 验收标准
- 测试设计
- 范围
- 关键文件
- 验证命令
- 项目上下文（技术栈，从 spec.md 提取）
- `execution-rules.md`
- `tdd-guardrails.md`
- `validation-policy.md`

## 必做事项

1. 先写测试，再运行测试确认 RED
2. 记录 RED 证据摘要
3. 只在里程碑范围内编写或修改实现代码
4. 按验证策略执行 lint/typecheck/test/build
5. 验证失败时只修改实现代码，不修改测试

## 禁止事项

- 直接改写 `.workflow/workflow.json`
- 直接改写 `.workflow/milestones.json`
- 直接改写 `.workflow/verify.json`
- 直接改写 `.workflow/events.jsonl`

## 返回格式

返回一个 JSON 对象，包含以下字段：

- `status`: `completed | failed | blocked`
- `red_evidence`: RED 阶段失败输出摘要
- `test_result`: `green | red`
- `verify_steps`: 实际执行的验证步骤列表
- `files_changed`: 修改文件列表
- `decisions`: 关键决策列表
- `failure_reason`: 失败或阻塞原因，没有则为 `null`
