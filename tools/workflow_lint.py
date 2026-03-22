#!/usr/bin/env python3
"""Validate .workflow state files and phase gates."""

import json
import os
import re
import sys
from datetime import datetime

from plan_sync import (
    REVISION_PATTERN,
    checksum_map_from_milestones,
    checksum_map_from_plan,
    parse_checksum_metadata,
)

VALID_PHASES = ["init", "planning", "executing", "verifying", "completed"]
VALID_WORKFLOW_STATUSES = ["running", "blocked", "paused", "failed"]
VALID_MILESTONE_STATUSES = ["pending", "in_progress", "completed", "failed"]
VALID_VERIFY_TYPES = ["lint", "typecheck", "test", "build"]
VALID_EVENT_TYPES = [
    "workflow_init",
    "spec_approved",
    "plan_generated",
    "plan_approved",
    "milestone_started",
    "milestone_red",
    "milestone_green",
    "milestone_verify",
    "milestone_completed",
    "milestone_failed",
    "verify_started",
    "verify_completed",
    "verify_failed",
    "phase_transition",
    "workflow_completed",
    "workflow_blocked",
    "workflow_resumed",
    "decision",
]
WORKFLOW_KEYS = {
    "phase",
    "status",
    "reason",
    "current_milestone_id",
    "spec_approved",
    "plan_approved",
    "verify_commands",
    "final_verify_overall",
    "updated_at",
}
MILESTONE_KEYS = {
    "id",
    "title",
    "status",
    "dependencies",
    "acceptance_criteria",
    "test_design",
    "scope",
    "key_files",
    "verify_commands",
    "red_evidence",
    "test_result",
    "verify_result_summary",
    "decision_log",
    "completed_at",
}
VERIFY_RUN_KEYS = {
    "id",
    "scope",
    "milestone_id",
    "started_at",
    "finished_at",
    "overall",
    "steps",
}
VERIFY_STEP_KEYS = {
    "type",
    "command",
    "exit_code",
    "started_at",
    "finished_at",
    "summary",
    "passed",
}
EVENT_KEYS = {
    "time",
    "type",
    "phase",
    "milestone_id",
    "summary",
    "artifacts",
}
MILESTONE_ID_PATTERN = re.compile(r"^M\d+$")


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        return None, f"JSON 解析失败: {path}: {exc}"


def load_jsonl(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"

    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            line = raw_line.strip()
            if not line:
                return None, f"JSONL 解析失败: {path}: 第 {line_number} 行为空行"
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                return None, f"JSONL 解析失败: {path}: 第 {line_number} 行: {exc}"
    return records, None


def is_datetime(value):
    if not isinstance(value, str):
        return False
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def validate_verify_commands(value, prefix, errors):
    if value is None:
        return
    if not isinstance(value, dict):
        errors.append(f"{prefix} 必须是对象")
        return

    extra = set(value.keys()) - set(VALID_VERIFY_TYPES)
    if extra:
        errors.append(f"{prefix} 包含未知键: {sorted(extra)}")

    for command_type, command in value.items():
        if command is not None and not isinstance(command, str):
            errors.append(f"{prefix}.{command_type} 必须是字符串或 null")


def validate_workflow(data, errors):
    if not isinstance(data, dict):
        errors.append("workflow.json 必须是对象")
        return

    extra = set(data.keys()) - WORKFLOW_KEYS
    if extra:
        errors.append(f"workflow.json 包含未知字段: {sorted(extra)}")

    for field in ["phase", "status", "updated_at"]:
        if field not in data:
            errors.append(f"workflow.json 缺少必需字段: {field}")

    phase = data.get("phase")
    if phase is not None and phase not in VALID_PHASES:
        errors.append(f"workflow.json phase 无效: {phase}")

    status = data.get("status")
    if status is not None and status not in VALID_WORKFLOW_STATUSES:
        errors.append(f"workflow.json status 无效: {status}")

    if status in ("blocked", "paused", "failed") and not data.get("reason"):
        errors.append(f"workflow.json status={status} 时必须提供 reason")

    current_milestone_id = data.get("current_milestone_id")
    if current_milestone_id is not None and not isinstance(current_milestone_id, str):
        errors.append("workflow.json current_milestone_id 必须是字符串或 null")

    for field in ["spec_approved", "plan_approved"]:
        if field in data and not isinstance(data[field], bool):
            errors.append(f"workflow.json {field} 必须是布尔值")

    validate_verify_commands(data.get("verify_commands"), "workflow.json verify_commands", errors)

    final_verify = data.get("final_verify_overall")
    if final_verify is not None and final_verify not in ("pass", "fail"):
        errors.append(f"workflow.json final_verify_overall 无效: {final_verify}")

    updated_at = data.get("updated_at")
    if updated_at is not None and not is_datetime(updated_at):
        errors.append("workflow.json updated_at 不是合法的 ISO 8601 时间")

    if current_milestone_id is not None:
        if not isinstance(current_milestone_id, str) or not MILESTONE_ID_PATTERN.match(current_milestone_id):
            errors.append(
                f"workflow.json current_milestone_id 格式无效: {current_milestone_id}"
            )

    if phase == "completed" and final_verify != "pass":
        errors.append("workflow.json phase=completed 时 final_verify_overall 必须为 pass")


def validate_milestones(data, errors):
    if not isinstance(data, dict):
        errors.append("milestones.json 必须是对象")
        return

    extra = set(data.keys()) - {"revision", "milestones"}
    if extra:
        errors.append(f"milestones.json 包含未知字段: {sorted(extra)}")

    revision = data.get("revision")
    if not isinstance(revision, int) or revision < 1:
        errors.append("milestones.json revision 必须是正整数")

    milestones = data.get("milestones")
    if not isinstance(milestones, list):
        errors.append("milestones.json milestones 必须是数组")
        return

    seen_ids = set()
    for index, milestone in enumerate(milestones):
        prefix = f"milestones.json milestones[{index}]"
        if not isinstance(milestone, dict):
            errors.append(f"{prefix} 必须是对象")
            continue

        extra_fields = set(milestone.keys()) - MILESTONE_KEYS
        if extra_fields:
            errors.append(f"{prefix} 包含未知字段: {sorted(extra_fields)}")

        for field in ["id", "title", "status"]:
            if field not in milestone:
                errors.append(f"{prefix} 缺少必需字段: {field}")

        milestone_id = milestone.get("id")
        if milestone_id is not None and not MILESTONE_ID_PATTERN.match(milestone_id):
            errors.append(f"{prefix} id 格式无效: {milestone_id}")
        if milestone_id in seen_ids:
            errors.append(f"{prefix} id 重复: {milestone_id}")
        if milestone_id is not None:
            seen_ids.add(milestone_id)

        title = milestone.get("title")
        if title is not None and not isinstance(title, str):
            errors.append(f"{prefix} title 必须是字符串")

        status = milestone.get("status")
        if status is not None and status not in VALID_MILESTONE_STATUSES:
            errors.append(f"{prefix} status 无效: {status}")

        dependencies = milestone.get("dependencies")
        if dependencies is not None:
            if not isinstance(dependencies, list):
                errors.append(f"{prefix} dependencies 必须是数组")
            else:
                for dep in dependencies:
                    if not isinstance(dep, str) or not MILESTONE_ID_PATTERN.match(dep):
                        errors.append(f"{prefix} dependencies 包含无效 ID: {dep}")

        for field in ["acceptance_criteria", "test_design", "scope", "key_files", "decision_log"]:
            value = milestone.get(field)
            if value is not None:
                if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                    errors.append(f"{prefix} {field} 必须是字符串数组")

        validate_verify_commands(
            milestone.get("verify_commands"),
            f"{prefix} verify_commands",
            errors,
        )

        red_evidence = milestone.get("red_evidence")
        if red_evidence is not None and not isinstance(red_evidence, str):
            errors.append(f"{prefix} red_evidence 必须是字符串或 null")

        test_result = milestone.get("test_result")
        if test_result is not None and test_result not in ("red", "green"):
            errors.append(f"{prefix} test_result 无效: {test_result}")

        verify_summary = milestone.get("verify_result_summary")
        if verify_summary is not None and not isinstance(verify_summary, str):
            errors.append(f"{prefix} verify_result_summary 必须是字符串或 null")

        completed_at = milestone.get("completed_at")
        if completed_at is not None and not is_datetime(completed_at):
            errors.append(f"{prefix} completed_at 不是合法的 ISO 8601 时间")

        # completed 状态的最小证据要求（建议5）
        if status == "completed":
            if not red_evidence:
                errors.append(f"{prefix} status=completed 时 red_evidence 不能为 null（TDD 先行证明缺失）")
            if test_result != "green":
                errors.append(f"{prefix} status=completed 时 test_result 必须为 green（当前: {test_result!r}）")
            if not completed_at:
                errors.append(f"{prefix} status=completed 时 completed_at 不能为 null")


def validate_verify(data, errors):
    if not isinstance(data, dict):
        errors.append("verify.json 必须是对象")
        return

    extra = set(data.keys()) - {"revision", "runs"}
    if extra:
        errors.append(f"verify.json 包含未知字段: {sorted(extra)}")

    revision = data.get("revision")
    if not isinstance(revision, int) or revision < 1:
        errors.append("verify.json revision 必须是正整数")

    runs = data.get("runs")
    if not isinstance(runs, list):
        errors.append("verify.json runs 必须是数组")
        return

    for run_index, run in enumerate(runs):
        prefix = f"verify.json runs[{run_index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} 必须是对象")
            continue

        extra_fields = set(run.keys()) - VERIFY_RUN_KEYS
        if extra_fields:
            errors.append(f"{prefix} 包含未知字段: {sorted(extra_fields)}")

        for field in ["id", "scope", "started_at", "overall", "steps"]:
            if field not in run:
                errors.append(f"{prefix} 缺少必需字段: {field}")

        if run.get("id") is not None and not isinstance(run["id"], str):
            errors.append(f"{prefix} id 必须是字符串")

        scope = run.get("scope")
        if scope is not None and scope not in ("milestone", "final"):
            errors.append(f"{prefix} scope 无效: {scope}")

        milestone_id = run.get("milestone_id")
        if milestone_id is not None and not isinstance(milestone_id, str):
            errors.append(f"{prefix} milestone_id 必须是字符串或 null")
        if scope == "milestone" and not milestone_id:
            errors.append(f"{prefix} scope=milestone 时必须提供 milestone_id")

        if "started_at" in run and not is_datetime(run["started_at"]):
            errors.append(f"{prefix} started_at 不是合法的 ISO 8601 时间")
        if run.get("finished_at") is not None and not is_datetime(run["finished_at"]):
            errors.append(f"{prefix} finished_at 不是合法的 ISO 8601 时间")

        overall = run.get("overall")
        if overall is not None and overall not in ("pass", "fail", "running"):
            errors.append(f"{prefix} overall 无效: {overall}")

        steps = run.get("steps")
        if not isinstance(steps, list):
            errors.append(f"{prefix} steps 必须是数组")
            continue

        for step_index, step in enumerate(steps):
            step_prefix = f"{prefix} steps[{step_index}]"
            if not isinstance(step, dict):
                errors.append(f"{step_prefix} 必须是对象")
                continue

            extra_step_fields = set(step.keys()) - VERIFY_STEP_KEYS
            if extra_step_fields:
                errors.append(f"{step_prefix} 包含未知字段: {sorted(extra_step_fields)}")

            for field in ["command", "type"]:
                if field not in step:
                    errors.append(f"{step_prefix} 缺少必需字段: {field}")

            step_type = step.get("type")
            if step_type is not None and step_type not in VALID_VERIFY_TYPES:
                errors.append(f"{step_prefix} type 无效: {step_type}")

            command = step.get("command")
            if command is not None and not isinstance(command, str):
                errors.append(f"{step_prefix} command 必须是字符串")

            exit_code = step.get("exit_code")
            if exit_code is not None and not isinstance(exit_code, int):
                errors.append(f"{step_prefix} exit_code 必须是整数或 null")

            for field in ["started_at", "finished_at"]:
                if step.get(field) is not None and not is_datetime(step[field]):
                    errors.append(f"{step_prefix} {field} 不是合法的 ISO 8601 时间")

            summary = step.get("summary")
            if summary is not None and not isinstance(summary, str):
                errors.append(f"{step_prefix} summary 必须是字符串或 null")

            passed = step.get("passed")
            if passed is not None and not isinstance(passed, bool):
                errors.append(f"{step_prefix} passed 必须是布尔值或 null")


def validate_events(data, errors, milestone_ids=None):
    if not isinstance(data, list):
        errors.append("events.jsonl 必须是 JSONL 记录数组")
        return

    known_milestone_ids = set(milestone_ids or [])
    for event_index, event in enumerate(data):
        prefix = f"events.jsonl[{event_index + 1}]"
        if not isinstance(event, dict):
            errors.append(f"{prefix} 必须是对象")
            continue

        extra_fields = set(event.keys()) - EVENT_KEYS
        if extra_fields:
            errors.append(f"{prefix} 包含未知字段: {sorted(extra_fields)}")

        for field in ["time", "type", "phase", "summary"]:
            if field not in event:
                errors.append(f"{prefix} 缺少必需字段: {field}")

        event_time = event.get("time")
        if event_time is not None and not is_datetime(event_time):
            errors.append(f"{prefix} time 不是合法的 ISO 8601 时间")

        event_type = event.get("type")
        if event_type is not None and event_type not in VALID_EVENT_TYPES:
            errors.append(f"{prefix} type 无效: {event_type}")

        phase = event.get("phase")
        if phase is not None and phase not in VALID_PHASES:
            errors.append(f"{prefix} phase 无效: {phase}")

        milestone_id = event.get("milestone_id")
        if milestone_id is not None:
            if not isinstance(milestone_id, str) or not MILESTONE_ID_PATTERN.match(milestone_id):
                errors.append(f"{prefix} milestone_id 格式无效: {milestone_id}")
            elif known_milestone_ids and milestone_id not in known_milestone_ids:
                errors.append(f"{prefix} milestone_id 未在 milestones.json 中定义: {milestone_id}")

        summary = event.get("summary")
        if summary is not None and not isinstance(summary, str):
            errors.append(f"{prefix} summary 必须是字符串")

        artifacts = event.get("artifacts")
        if artifacts is not None and not isinstance(artifacts, dict):
            errors.append(f"{prefix} artifacts 必须是对象或 null")


def check_phase_preconditions(workflow, target_phase, errors):
    current_phase = workflow.get("phase")
    phase_order = {phase: index for index, phase in enumerate(VALID_PHASES)}

    if target_phase not in phase_order:
        errors.append(f"目标阶段无效: {target_phase}")
        return

    if current_phase and phase_order.get(current_phase, -1) > phase_order[target_phase]:
        errors.append(f"不允许回退: {current_phase} -> {target_phase}")

    if target_phase == "planning" and not workflow.get("spec_approved"):
        errors.append("进入 planning 阶段需要 spec_approved == true")
    if target_phase == "executing" and not workflow.get("plan_approved"):
        errors.append("进入 executing 阶段需要 plan_approved == true")
    if target_phase == "completed" and workflow.get("final_verify_overall") != "pass":
        errors.append("进入 completed 阶段需要 final_verify_overall == pass")


def check_plan_consistency(workflow_dir, errors):
    plan_path = os.path.join(workflow_dir, "plan.md")
    milestones_path = os.path.join(workflow_dir, "milestones.json")
    if not os.path.exists(plan_path) or not os.path.exists(milestones_path):
        return

    milestones_data, err = load_json(milestones_path)
    if err:
        errors.append(err)
        return

    with open(plan_path, "r", encoding="utf-8") as handle:
        plan_content = handle.read()

    revision_match = REVISION_PATTERN.search(plan_content)
    if not revision_match:
        errors.append("plan.md 缺少 milestones_revision 元数据标记")
    else:
        plan_revision = int(revision_match.group(1))
        json_revision = milestones_data.get("revision", 0)
        if plan_revision != json_revision:
            errors.append(
                f"plan.md 的 milestones_revision ({plan_revision}) "
                f"与 milestones.json revision ({json_revision}) 不一致"
            )

    checksum_metadata, err = parse_checksum_metadata(plan_content)
    if err:
        errors.append(err)
        return

    expected_checksums = checksum_map_from_milestones(milestones_data.get("milestones", []))
    for milestone_id, checksum in checksum_metadata.items():
        current_checksum = expected_checksums.get(milestone_id)
        if current_checksum is not None and current_checksum != checksum:
            errors.append(f"plan.md 中 {milestone_id} 的 checksum 与 milestones.json 不一致")

    actual_checksums = checksum_map_from_plan(plan_content, checksum_metadata.keys())
    for milestone_id, actual_checksum in actual_checksums.items():
        if checksum_metadata.get(milestone_id) != actual_checksum:
            errors.append(f"plan.md 中 {milestone_id} 的只读投影内容已被修改")

    for milestone in milestones_data.get("milestones", []):
        milestone_id = milestone.get("id", "")
        if milestone_id and milestone_id not in plan_content:
            errors.append(f"milestones.json 中的 {milestone_id} 在 plan.md 中未找到")


def check_completed_consistency(workflow, milestones, verify, errors):
    if not workflow or workflow.get("phase") != "completed":
        return

    current_milestone_id = workflow.get("current_milestone_id")
    if current_milestone_id is not None:
        errors.append("workflow.json phase=completed 时 current_milestone_id 必须为 null")

    if not isinstance(milestones, dict):
        errors.append("workflow.json phase=completed 时必须存在合法的 milestones.json")
    else:
        open_milestones = [
            milestone.get("id", f"#{index}")
            for index, milestone in enumerate(milestones.get("milestones", []), 1)
            if milestone.get("status") != "completed"
        ]
        if open_milestones:
            errors.append(
                "workflow.json phase=completed 时所有里程碑必须为 completed: "
                f"{open_milestones}"
            )

    if not isinstance(verify, dict):
        errors.append("workflow.json phase=completed 时必须存在合法的 verify.json")
        return

    final_pass_run = next(
        (
            run
            for run in verify.get("runs", [])
            if run.get("scope") == "final" and run.get("overall") == "pass"
        ),
        None,
    )
    if final_pass_run is None:
        errors.append("workflow.json phase=completed 时 verify.json 必须存在 final pass run")


def check_milestone_verify_records(milestones, verify, errors):
    """检查已完成的里程碑在 verify.json 中是否有对应的 milestone pass 记录。"""
    if not isinstance(milestones, dict) or not isinstance(verify, dict):
        return

    runs = verify.get("runs", [])
    if not isinstance(runs, list):
        return

    # 收集每个里程碑的 pass 记录
    passed_milestones = set()
    for run in runs:
        if (
            isinstance(run, dict)
            and run.get("scope") == "milestone"
            and run.get("overall") == "pass"
            and run.get("milestone_id")
        ):
            passed_milestones.add(run["milestone_id"])

    # 检查每个 completed 里程碑
    for milestone in milestones.get("milestones", []):
        if not isinstance(milestone, dict):
            continue
        if milestone.get("status") != "completed":
            continue
        milestone_id = milestone.get("id")
        if milestone_id and milestone_id not in passed_milestones:
            errors.append(
                f"{milestone_id} status=completed 但 verify.json 中没有对应的 "
                f"scope=milestone pass 记录"
            )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="工作流状态校验")
    parser.add_argument("phase", nargs="?", help="目标阶段（可选，用于前置条件校验）")
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    workflow_dir = args.workflow_dir
    errors = []

    workflow_path = os.path.join(workflow_dir, "workflow.json")
    workflow_data, err = load_json(workflow_path)
    if err:
        errors.append(err)
    else:
        validate_workflow(workflow_data, errors)

    milestones_path = os.path.join(workflow_dir, "milestones.json")
    milestones_data, err = load_json(milestones_path)
    if err:
        if os.path.exists(milestones_path):
            errors.append(err)
    else:
        validate_milestones(milestones_data, errors)

    verify_path = os.path.join(workflow_dir, "verify.json")
    verify_data, err = load_json(verify_path)
    if err:
        if os.path.exists(verify_path):
            errors.append(err)
    else:
        validate_verify(verify_data, errors)

    milestone_ids = []
    if isinstance(milestones_data, dict):
        milestone_ids = [
            milestone.get("id")
            for milestone in milestones_data.get("milestones", [])
            if isinstance(milestone, dict) and milestone.get("id")
        ]

    events_path = os.path.join(workflow_dir, "events.jsonl")
    events_data, err = load_jsonl(events_path)
    if err:
        errors.append(err)
    else:
        validate_events(events_data, errors, milestone_ids)

    if args.phase and workflow_data:
        check_phase_preconditions(workflow_data, args.phase, errors)

    check_plan_consistency(workflow_dir, errors)
    check_completed_consistency(workflow_data, milestones_data, verify_data, errors)
    check_milestone_verify_records(milestones_data, verify_data, errors)

    if errors:
        print(f"LINT FAILED ({len(errors)} 个问题):", file=sys.stderr)
        for index, error in enumerate(errors, 1):
            print(f"  {index}. {error}", file=sys.stderr)
        sys.exit(1)

    print("LINT PASSED: 所有校验通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
