#!/usr/bin/env python3
"""workflow_gate.py - 里程碑完成门禁

用法：
  python tools/workflow_gate.py milestone <id> [--workflow-dir .workflow]

职责：
  - 里程碑是否允许完成
  - 是否存在 RED 证据
  - 是否有测试工件变化
  - 是否有实际验证结果
"""

import json
import sys
import os


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {path}: {e}"


def gate_milestone(milestone_id, workflow_dir):
    """检查里程碑是否允许标记为完成"""
    errors = []

    # 加载 milestones.json
    ms_path = os.path.join(workflow_dir, "milestones.json")
    ms_data, err = load_json(ms_path)
    if err:
        return [err]

    # 找到目标里程碑
    milestone = None
    for m in ms_data.get("milestones", []):
        if m.get("id") == milestone_id:
            milestone = m
            break

    if milestone is None:
        return [f"里程碑 {milestone_id} 不存在"]

    # 检查依赖是否全部完成
    deps = milestone.get("dependencies", [])
    if deps:
        all_milestones = {m["id"]: m for m in ms_data.get("milestones", [])}
        for dep_id in deps:
            dep = all_milestones.get(dep_id)
            if dep is None:
                errors.append(f"依赖 {dep_id} 不存在")
            elif dep.get("status") != "completed":
                errors.append(f"依赖 {dep_id} 未完成（状态: {dep.get('status')}）")

    # 检查 RED 证据
    if not milestone.get("red_evidence"):
        errors.append(f"{milestone_id} 缺少 RED 证据（测试先行的证明）")

    # 检查测试结果
    test_result = milestone.get("test_result")
    if test_result != "green":
        errors.append(f"{milestone_id} 测试结果不是 green（当前: {test_result}）")

    # 检查验证结果
    verify_summary = milestone.get("verify_result_summary")
    if not verify_summary:
        errors.append(f"{milestone_id} 缺少验证结果摘要")

    # 加载 verify.json 检查是否有实际验证记录
    vf_path = os.path.join(workflow_dir, "verify.json")
    vf_data, err = load_json(vf_path)
    if err:
        if os.path.exists(vf_path):
            errors.append(err)
        else:
            errors.append(f"{milestone_id} 没有 verify.json 中的验证记录")
    else:
        # 检查是否有该里程碑的通过验证记录
        has_pass = False
        for run in vf_data.get("runs", []):
            if (
                run.get("milestone_id") == milestone_id
                and run.get("overall") == "pass"
            ):
                has_pass = True
                break
        if not has_pass:
            errors.append(f"{milestone_id} 在 verify.json 中没有通过的验证记录")

    # 检查 workflow.json 前置条件
    wf_path = os.path.join(workflow_dir, "workflow.json")
    wf_data, err = load_json(wf_path)
    if err:
        errors.append(err)
    else:
        if not wf_data.get("plan_approved"):
            errors.append("workflow.json plan_approved 不为 true，不允许完成里程碑")
        if wf_data.get("phase") != "executing":
            errors.append(f"workflow.json phase 不是 executing（当前: {wf_data.get('phase')}）")

    return errors


def main():
    import argparse

    parser = argparse.ArgumentParser(description="里程碑完成门禁")
    parser.add_argument("command", choices=["milestone"], help="门禁类型")
    parser.add_argument("id", help="里程碑 ID（如 M0, M1）")
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    errors = gate_milestone(args.id, args.workflow_dir)

    if errors:
        print(f"GATE FAILED for {args.id} ({len(errors)} 个问题):", file=sys.stderr)
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"GATE PASSED: {args.id} 允许标记为完成")
        sys.exit(0)


if __name__ == "__main__":
    main()
