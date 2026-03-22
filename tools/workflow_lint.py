#!/usr/bin/env python3
"""workflow_lint.py - 工作流状态校验工具

用法：
  python tools/workflow_lint.py <phase> [--workflow-dir .workflow]

职责：
  - schema 校验（workflow.json, milestones.json, verify.json）
  - phase 前置条件校验
  - 派生 Markdown 与 JSON 一致性校验
"""

import json
import sys
import os
import re
from datetime import datetime

VALID_PHASES = ["init", "planning", "executing", "verifying", "completed"]
VALID_STATUSES = ["running", "blocked", "paused", "failed"]
VALID_MILESTONE_STATUSES = ["pending", "in_progress", "completed", "failed"]
MILESTONE_ID_PATTERN = re.compile(r"^M\d+$")


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {path}: {e}"


def validate_workflow(data, errors):
    """校验 workflow.json"""
    required = ["phase", "status", "updated_at"]
    for field in required:
        if field not in data:
            errors.append(f"workflow.json 缺少必需字段: {field}")

    phase = data.get("phase")
    if phase and phase not in VALID_PHASES:
        errors.append(f"workflow.json phase 无效: {phase}，允许值: {VALID_PHASES}")

    status = data.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"workflow.json status 无效: {status}，允许值: {VALID_STATUSES}")

    if status in ("blocked", "paused", "failed") and not data.get("reason"):
        errors.append(f"workflow.json status={status} 时必须提供 reason")

    if phase == "completed" and data.get("final_verify_overall") != "pass":
        errors.append("workflow.json phase=completed 时 final_verify_overall 必须为 pass")

    verify_cmds = data.get("verify_commands")
    if verify_cmds is not None:
        if not isinstance(verify_cmds, dict):
            errors.append("workflow.json verify_commands 必须是对象")
        else:
            allowed_keys = {"lint", "typecheck", "test", "build"}
            extra = set(verify_cmds.keys()) - allowed_keys
            if extra:
                errors.append(f"workflow.json verify_commands 包含未知键: {extra}")

    fvo = data.get("final_verify_overall")
    if fvo is not None and fvo not in ("pass", "fail"):
        errors.append(f"workflow.json final_verify_overall 无效: {fvo}")


def validate_milestones(data, errors):
    """校验 milestones.json"""
    if "revision" not in data:
        errors.append("milestones.json 缺少必需字段: revision")
    elif not isinstance(data["revision"], int) or data["revision"] < 1:
        errors.append("milestones.json revision 必须是正整数")

    if "milestones" not in data:
        errors.append("milestones.json 缺少必需字段: milestones")
        return

    if not isinstance(data["milestones"], list):
        errors.append("milestones.json milestones 必须是数组")
        return

    ids_seen = set()
    for i, m in enumerate(data["milestones"]):
        prefix = f"milestones.json milestones[{i}]"
        if not isinstance(m, dict):
            errors.append(f"{prefix} 必须是对象")
            continue

        for field in ["id", "title", "status"]:
            if field not in m:
                errors.append(f"{prefix} 缺少必需字段: {field}")

        mid = m.get("id", "")
        if mid and not MILESTONE_ID_PATTERN.match(mid):
            errors.append(f"{prefix} id 格式无效: {mid}，应为 M0, M1, M2...")

        if mid in ids_seen:
            errors.append(f"{prefix} id 重复: {mid}")
        ids_seen.add(mid)

        status = m.get("status")
        if status and status not in VALID_MILESTONE_STATUSES:
            errors.append(f"{prefix} status 无效: {status}")

        deps = m.get("dependencies", [])
        if deps and not isinstance(deps, list):
            errors.append(f"{prefix} dependencies 必须是数组")
        elif deps:
            for dep in deps:
                if not MILESTONE_ID_PATTERN.match(dep):
                    errors.append(f"{prefix} dependencies 包含无效 ID: {dep}")


def validate_verify(data, errors):
    """校验 verify.json"""
    if "revision" not in data:
        errors.append("verify.json 缺少必需字段: revision")

    if "runs" not in data:
        errors.append("verify.json 缺少必需字段: runs")
        return

    if not isinstance(data["runs"], list):
        errors.append("verify.json runs 必须是数组")
        return

    for i, run in enumerate(data["runs"]):
        prefix = f"verify.json runs[{i}]"
        for field in ["id", "scope", "started_at", "steps"]:
            if field not in run:
                errors.append(f"{prefix} 缺少必需字段: {field}")

        scope = run.get("scope")
        if scope and scope not in ("milestone", "final"):
            errors.append(f"{prefix} scope 无效: {scope}")

        if scope == "milestone" and not run.get("milestone_id"):
            errors.append(f"{prefix} scope=milestone 时必须提供 milestone_id")

        steps = run.get("steps", [])
        if not isinstance(steps, list):
            errors.append(f"{prefix} steps 必须是数组")
        else:
            for j, step in enumerate(steps):
                step_prefix = f"{prefix} steps[{j}]"
                if "command" not in step:
                    errors.append(f"{step_prefix} 缺少必需字段: command")
                if "type" not in step:
                    errors.append(f"{step_prefix} 缺少必需字段: type")
                elif step["type"] not in ("lint", "typecheck", "test", "build"):
                    errors.append(f"{step_prefix} type 无效: {step['type']}")


def check_phase_preconditions(workflow, target_phase, errors):
    """检查阶段转换的前置条件"""
    current_phase = workflow.get("phase")

    phase_order = {p: i for i, p in enumerate(VALID_PHASES)}

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
    """检查 plan.md 与 milestones.json 的一致性"""
    plan_path = os.path.join(workflow_dir, "plan.md")
    milestones_path = os.path.join(workflow_dir, "milestones.json")

    if not os.path.exists(plan_path) or not os.path.exists(milestones_path):
        return

    milestones_data, err = load_json(milestones_path)
    if err:
        return

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_content = f.read()

    # 检查 plan.md 中的 milestones_revision 元数据
    revision_match = re.search(r"<!-- milestones_revision:\s*(\d+)\s*-->", plan_content)
    if not revision_match:
        errors.append("plan.md 缺少 milestones_revision 元数据标记")
    else:
        plan_rev = int(revision_match.group(1))
        json_rev = milestones_data.get("revision", 0)
        if plan_rev != json_rev:
            errors.append(
                f"plan.md 的 milestones_revision ({plan_rev}) "
                f"与 milestones.json revision ({json_rev}) 不一致"
            )

    # 检查里程碑 ID 是否全部出现在 plan.md 中
    for m in milestones_data.get("milestones", []):
        mid = m.get("id", "")
        if mid and mid not in plan_content:
            errors.append(f"milestones.json 中的 {mid} 在 plan.md 中未找到")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="工作流状态校验")
    parser.add_argument("phase", nargs="?", help="目标阶段（可选，用于前置条件校验）")
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    workflow_dir = args.workflow_dir
    errors = []

    # 校验 workflow.json
    wf_path = os.path.join(workflow_dir, "workflow.json")
    workflow_data, err = load_json(wf_path)
    if err:
        errors.append(err)
    else:
        validate_workflow(workflow_data, errors)

    # 校验 milestones.json
    ms_path = os.path.join(workflow_dir, "milestones.json")
    ms_data, err = load_json(ms_path)
    if err:
        if os.path.exists(ms_path):
            errors.append(err)
    else:
        validate_milestones(ms_data, errors)

    # 校验 verify.json
    vf_path = os.path.join(workflow_dir, "verify.json")
    vf_data, err = load_json(vf_path)
    if err:
        if os.path.exists(vf_path):
            errors.append(err)
    else:
        validate_verify(vf_data, errors)

    # 阶段前置条件校验
    if args.phase and workflow_data:
        check_phase_preconditions(workflow_data, args.phase, errors)

    # plan.md 与 milestones.json 一致性校验
    check_plan_consistency(workflow_dir, errors)

    # 输出结果
    if errors:
        print(f"LINT FAILED ({len(errors)} 个问题):", file=sys.stderr)
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("LINT PASSED: 所有校验通过")
        sys.exit(0)


if __name__ == "__main__":
    main()
