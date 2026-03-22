#!/usr/bin/env python3
"""workflow_confirm.py - 用户确认门禁

用法：
  python tools/workflow_confirm.py spec [--workflow-dir .workflow]
  python tools/workflow_confirm.py plan [--workflow-dir .workflow]

职责：
  - 将 spec_approved 或 plan_approved 置为 true
  - 记录确认事件到 events.jsonl
  - 更新 workflow.json
"""

import json
import sys
import os
from datetime import datetime, timezone


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {path}: {e}"


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def append_event(workflow_dir, event):
    events_path = os.path.join(workflow_dir, "events.jsonl")
    with open(events_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def confirm_spec(workflow_dir):
    """确认 spec.md"""
    wf_path = os.path.join(workflow_dir, "workflow.json")
    wf_data, err = load_json(wf_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # 检查 spec.md 是否存在
    spec_path = os.path.join(workflow_dir, "spec.md")
    if not os.path.exists(spec_path):
        print(f"ERROR: {spec_path} 不存在", file=sys.stderr)
        return 1

    # 检查 spec.md 是否还是空模板
    with open(spec_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "{{PROJECT_NAME}}" in content or "{{GOAL_DESCRIPTION}}" in content:
        print("ERROR: spec.md 仍包含未填充的模板占位符", file=sys.stderr)
        return 1

    if wf_data.get("spec_approved"):
        print("spec 已经确认过了", file=sys.stderr)
        return 0

    now = datetime.now(timezone.utc).isoformat()

    # 更新 workflow.json
    wf_data["spec_approved"] = True
    wf_data["updated_at"] = now

    # 如果当前在 init 阶段，推进到 planning
    if wf_data.get("phase") == "init":
        wf_data["phase"] = "planning"

    save_json(wf_path, wf_data)

    # 记录事件
    append_event(workflow_dir, {
        "time": now,
        "type": "spec_approved",
        "phase": wf_data["phase"],
        "milestone_id": None,
        "summary": "用户确认 spec.md",
    })

    print(f"CONFIRMED: spec_approved = true")
    print(f"  workflow.json 已更新，phase = {wf_data['phase']}")
    return 0


def confirm_plan(workflow_dir):
    """确认 plan.md"""
    wf_path = os.path.join(workflow_dir, "workflow.json")
    wf_data, err = load_json(wf_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    # 前置条件：spec 必须已确认
    if not wf_data.get("spec_approved"):
        print("ERROR: spec 尚未确认，不能确认 plan", file=sys.stderr)
        return 1

    # 检查 plan.md 是否存在
    plan_path = os.path.join(workflow_dir, "plan.md")
    if not os.path.exists(plan_path):
        print(f"ERROR: {plan_path} 不存在", file=sys.stderr)
        return 1

    # 检查 milestones.json 是否存在且有里程碑
    ms_path = os.path.join(workflow_dir, "milestones.json")
    ms_data, err = load_json(ms_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    milestones = ms_data.get("milestones", [])
    if not milestones:
        print("ERROR: milestones.json 中没有里程碑", file=sys.stderr)
        return 1

    if wf_data.get("plan_approved"):
        print("plan 已经确认过了", file=sys.stderr)
        return 0

    now = datetime.now(timezone.utc).isoformat()

    # 更新 workflow.json
    wf_data["plan_approved"] = True
    wf_data["updated_at"] = now

    # 如果当前在 planning 阶段，推进到 executing
    if wf_data.get("phase") == "planning":
        wf_data["phase"] = "executing"
        # 设置第一个里程碑
        first_pending = next(
            (m for m in milestones if m.get("status") == "pending"), None
        )
        if first_pending:
            wf_data["current_milestone_id"] = first_pending["id"]

    save_json(wf_path, wf_data)

    # 记录事件
    append_event(workflow_dir, {
        "time": now,
        "type": "plan_approved",
        "phase": wf_data["phase"],
        "milestone_id": None,
        "summary": f"用户确认 plan.md（{len(milestones)} 个里程碑）",
    })

    print(f"CONFIRMED: plan_approved = true")
    print(f"  workflow.json 已更新，phase = {wf_data['phase']}")
    if wf_data.get("current_milestone_id"):
        print(f"  首个里程碑: {wf_data['current_milestone_id']}")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="用户确认门禁")
    parser.add_argument(
        "target", choices=["spec", "plan"], help="确认目标"
    )
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    if args.target == "spec":
        sys.exit(confirm_spec(args.workflow_dir))
    else:
        sys.exit(confirm_plan(args.workflow_dir))


if __name__ == "__main__":
    main()
