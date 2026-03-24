#!/usr/bin/env python3
"""User confirmation gates for spec.md and plan.md."""

import json
import os
import sys
from datetime import datetime, timezone

from plan_sync import import_plan
from workflow_lint import lint_workflow_dir


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {path}: {exc}"


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def append_event(workflow_dir, event):
    events_path = os.path.join(workflow_dir, "events.jsonl")
    with open(events_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def confirm_spec(workflow_dir):
    workflow_path = os.path.join(workflow_dir, "workflow.json")
    workflow_data, err = load_json(workflow_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    spec_path = os.path.join(workflow_dir, "spec.md")
    if not os.path.exists(spec_path):
        print(f"ERROR: {spec_path} 不存在", file=sys.stderr)
        return 1

    with open(spec_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    if "{{PROJECT_NAME}}" in content or "{{GOAL_DESCRIPTION}}" in content:
        print("ERROR: spec.md 仍包含未填充的模板占位符", file=sys.stderr)
        return 1

    if workflow_data.get("spec_approved"):
        print("spec 已经确认过了", file=sys.stderr)
        return 0

    now = datetime.now(timezone.utc).isoformat()
    workflow_data["spec_approved"] = True
    workflow_data["updated_at"] = now
    if workflow_data.get("phase") == "init":
        workflow_data["phase"] = "planning"

    save_json(workflow_path, workflow_data)
    append_event(
        workflow_dir,
        {
            "time": now,
            "type": "spec_approved",
            "phase": workflow_data["phase"],
            "milestone_id": None,
            "summary": "用户确认 spec.md",
        },
    )

    print("CONFIRMED: spec_approved = true")
    print(f"  workflow.json 已更新，phase = {workflow_data['phase']}")
    return 0


def confirm_plan(workflow_dir):
    workflow_path = os.path.join(workflow_dir, "workflow.json")
    workflow_data, err = load_json(workflow_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if not workflow_data.get("spec_approved"):
        print("ERROR: spec 尚未确认，不能确认 plan", file=sys.stderr)
        return 1

    plan_path = os.path.join(workflow_dir, "plan.md")
    if not os.path.exists(plan_path):
        print(f"ERROR: {plan_path} 不存在", file=sys.stderr)
        return 1

    if workflow_data.get("plan_approved"):
        print("plan 已经确认过了", file=sys.stderr)
        return 0

    import_result = import_plan(workflow_dir)
    if import_result != 0:
        print("ERROR: plan.md 未通过同步校验，不能确认 plan", file=sys.stderr)
        return 1

    lint_errors, lint_warnings = lint_workflow_dir(workflow_dir)
    if lint_errors:
        print("ERROR: plan.md 导入后未通过 lint 校验，不能确认 plan", file=sys.stderr)
        for index, error in enumerate(lint_errors, 1):
            print(f"  {index}. {error}", file=sys.stderr)
        return 1
    if lint_warnings:
        print(f"LINT WARNINGS ({len(lint_warnings)} 个提示):", file=sys.stderr)
        for index, warning in enumerate(lint_warnings, 1):
            print(f"  {index}. {warning}", file=sys.stderr)

    milestones_path = os.path.join(workflow_dir, "milestones.json")
    milestones_data, err = load_json(milestones_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    milestones = milestones_data.get("milestones", [])
    if not milestones:
        print("ERROR: milestones.json 中没有里程碑", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat()
    workflow_data["plan_approved"] = True
    workflow_data["updated_at"] = now

    if workflow_data.get("phase") == "planning":
        workflow_data["phase"] = "executing"
        first_open = next(
            (milestone for milestone in milestones if milestone.get("status") != "completed"),
            None,
        )
        if first_open:
            workflow_data["current_milestone_id"] = first_open["id"]

    save_json(workflow_path, workflow_data)
    append_event(
        workflow_dir,
        {
            "time": now,
            "type": "plan_approved",
            "phase": workflow_data["phase"],
            "milestone_id": None,
            "summary": (
                f"用户确认 plan.md（{len(milestones)} 个里程碑，"
                f"revision={milestones_data.get('revision')}）"
            ),
        },
    )

    print("CONFIRMED: plan_approved = true")
    print(f"  workflow.json 已更新，phase = {workflow_data['phase']}")
    if workflow_data.get("current_milestone_id"):
        print(f"  首个里程碑: {workflow_data['current_milestone_id']}")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="用户确认门禁")
    parser.add_argument("target", choices=["spec", "plan"], help="确认目标")
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    if args.target == "spec":
        sys.exit(confirm_spec(args.workflow_dir))
    sys.exit(confirm_plan(args.workflow_dir))


if __name__ == "__main__":
    main()
