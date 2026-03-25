#!/usr/bin/env python3
"""Resume a blocked/paused/failed workflow with deterministic checks."""

import json
import os
import sys
from datetime import datetime, timezone

from workflow_lint import lint_workflow_dir

RESUMABLE_STATUSES = {"blocked", "paused", "failed"}


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


def _load_milestones(workflow_dir):
    milestones_path = os.path.join(workflow_dir, "milestones.json")
    data, err = load_json(milestones_path)
    if err:
        return None, err
    if not isinstance(data, dict):
        return None, "milestones.json 必须是对象"
    milestones = data.get("milestones")
    if not isinstance(milestones, list):
        return None, "milestones.json.milestones 必须是数组"
    return data, None


def _resume_specific_checks(workflow_dir, workflow_data):
    errors = []
    phase = workflow_data.get("phase")
    current_milestone_id = workflow_data.get("current_milestone_id")

    if phase == "completed":
        errors.append("phase=completed 的工作流不允许恢复")
        return errors

    milestones_data = None
    if phase in ("executing", "verifying"):
        milestones_data, err = _load_milestones(workflow_dir)
        if err:
            errors.append(err)
            return errors

    if phase == "executing":
        milestones = milestones_data.get("milestones", [])
        milestone_map = {
            milestone.get("id"): milestone
            for milestone in milestones
            if isinstance(milestone, dict) and milestone.get("id")
        }
        failed_ids = [
            milestone.get("id")
            for milestone in milestones
            if isinstance(milestone, dict) and milestone.get("status") == "failed"
        ]
        if current_milestone_id:
            current = milestone_map.get(current_milestone_id)
            if current is None:
                errors.append(
                    f"current_milestone_id={current_milestone_id} 在 milestones.json 中不存在"
                )
            elif current.get("status") == "completed":
                errors.append(
                    f"current_milestone_id={current_milestone_id} 已是 completed，"
                    "不能直接恢复 executing"
                )
            other_failed = [mid for mid in failed_ids if mid != current_milestone_id]
            if other_failed:
                errors.append(
                    "executing 阶段存在未处理的 failed 里程碑，"
                    f"不能恢复到 {current_milestone_id} 并绕过: {other_failed}"
                )
        elif failed_ids:
            errors.append(
                "executing 阶段存在 failed 里程碑但 current_milestone_id 为空，"
                f"不能恢复并跳过失败项: {failed_ids}"
            )
        elif not any(
            milestone.get("status") in ("pending", "in_progress")
            for milestone in milestones
            if isinstance(milestone, dict)
        ):
            errors.append("executing 阶段没有可恢复的里程碑")

    if phase == "verifying":
        milestones = milestones_data.get("milestones", [])
        open_milestones = [
            milestone.get("id", "?")
            for milestone in milestones
            if isinstance(milestone, dict) and milestone.get("status") != "completed"
        ]
        if open_milestones:
            errors.append(
                "verifying 阶段恢复前要求所有里程碑已完成，"
                f"当前未完成: {open_milestones}"
            )
        if current_milestone_id is not None:
            errors.append("verifying 阶段恢复前 current_milestone_id 必须为 null")

    return errors


def resume_workflow(workflow_dir):
    workflow_path = os.path.join(workflow_dir, "workflow.json")
    workflow_data, err = load_json(workflow_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if not isinstance(workflow_data, dict):
        print("ERROR: workflow.json 必须是对象", file=sys.stderr)
        return 1

    status = workflow_data.get("status")
    if status not in RESUMABLE_STATUSES:
        print(
            "ERROR: 只有 status=blocked/paused/failed 的工作流才能恢复，"
            f"当前为 {status!r}",
            file=sys.stderr,
        )
        return 1

    phase = workflow_data.get("phase")
    errors, warnings = lint_workflow_dir(workflow_dir, phase)
    errors.extend(_resume_specific_checks(workflow_dir, workflow_data))
    if errors:
        print("ERROR: 工作流未通过恢复前校验，不能恢复", file=sys.stderr)
        for index, error in enumerate(errors, 1):
            print(f"  {index}. {error}", file=sys.stderr)
        return 1

    if warnings:
        print(f"LINT WARNINGS ({len(warnings)} 个提示):", file=sys.stderr)
        for index, warning in enumerate(warnings, 1):
            print(f"  {index}. {warning}", file=sys.stderr)

    old_status = status
    old_reason = workflow_data.get("reason")
    now = datetime.now(timezone.utc).isoformat()

    workflow_data["status"] = "running"
    workflow_data["updated_at"] = now
    workflow_data.pop("reason", None)

    save_json(workflow_path, workflow_data)
    append_event(
        workflow_dir,
        {
            "time": now,
            "type": "workflow_resumed",
            "phase": phase,
            "milestone_id": workflow_data.get("current_milestone_id"),
            "summary": f"工作流从 {old_status} 恢复为 running",
            "artifacts": {
                "previous_status": old_status,
                "previous_reason": old_reason,
            },
        },
    )

    print("RESUMED: workflow status = running")
    print(f"  phase = {phase}")
    if workflow_data.get("current_milestone_id"):
        print(f"  current_milestone_id = {workflow_data['current_milestone_id']}")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="恢复被阻塞/暂停/失败的工作流")
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()
    sys.exit(resume_workflow(args.workflow_dir))


if __name__ == "__main__":
    main()
