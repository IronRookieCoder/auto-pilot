#!/usr/bin/env python3
"""Synchronize .workflow/plan.md and .workflow/milestones.json."""

import hashlib
import json
import os
import re
import sys

STATUS_EMOJI = {
    "pending": "🔲 待开始",
    "in_progress": "🔶 进行中",
    "completed": "✅ 已完成",
    "failed": "❌ 失败",
}

EMOJI_TO_STATUS = {
    "🔲": "pending",
    "🔶": "in_progress",
    "✅": "completed",
    "❌": "failed",
}

PLAN_EDITABLE_FIELDS = {
    "title",
    "dependencies",
    "acceptance_criteria",
    "test_design",
    "scope",
}
PRESERVED_FIELDS = {
    "status",
    "key_files",
    "verify_commands",
    "red_evidence",
    "test_result",
    "verify_result_summary",
    "decision_log",
    "completed_at",
}

REVISION_PATTERN = re.compile(r"<!-- milestones_revision:\s*(\d+)\s*-->")
CHECKSUM_PATTERN = re.compile(r"<!-- plan_sync_checksums:\s*(\{.*\})\s*-->")
MILESTONE_HEADER_PATTERN = re.compile(r"###\s+(M\d+):\s+(.+)")
COMPLETED_PATTERN = re.compile(
    r"✅\s+(M\d+):\s+(.+?)\s*\|.*?完成于\s*(\S*)\s*\|.*?决策:\s*(.*)"
)


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


def canonical_json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum_for_value(data):
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def machine_owned_projection_for_milestone(milestone):
    status = milestone.get("status", "pending")
    projection = {
        "status": status,
        "key_files": milestone.get("key_files", []),
        "verify_commands": milestone.get("verify_commands", {}),
        "decision_log": milestone.get("decision_log", []),
        "completed_at": milestone.get("completed_at"),
    }
    if status == "completed":
        projection["title"] = milestone.get("title", "")
    return projection


def checksum_map_from_milestones(milestones):
    return {
        milestone["id"]: checksum_for_value(
            machine_owned_projection_for_milestone(milestone)
        )
        for milestone in milestones
        if "id" in milestone
    }


def parse_checksum_metadata(plan_content):
    match = CHECKSUM_PATTERN.search(plan_content)
    if not match:
        return None, "plan.md 缺少 plan_sync_checksums 元数据"

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return None, f"plan.md checksum 元数据解析失败: {exc}"

    if not isinstance(data, dict):
        return None, "plan.md checksum 元数据必须是对象"

    for milestone_id, checksum in data.items():
        if not re.match(r"^M\d+$", milestone_id):
            return None, f"plan.md checksum 元数据包含无效里程碑 ID: {milestone_id}"
        if not isinstance(checksum, str) or not re.match(r"^[0-9a-f]{64}$", checksum):
            return None, f"plan.md checksum 元数据包含无效 checksum: {milestone_id}"

    return data, None


def parse_checkbox_section(section, title):
    lines = section.splitlines()
    header = f"- **{title}**："
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue

        items = []
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor]
            if current.startswith("  - [ ] ") or current.startswith("  - [x] "):
                items.append(current.split("] ", 1)[1].strip())
                cursor += 1
                continue
            break
        return items

    return []


def parse_bullet_section(section, title):
    lines = section.splitlines()
    header = f"- **{title}**："
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue

        items = []
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor]
            if current.startswith("  - "):
                items.append(current[4:].strip())
                cursor += 1
                continue
            break
        return items

    return []


def parse_verify_commands(section):
    lines = section.splitlines()
    header = "- **验证命令**："
    for index, line in enumerate(lines):
        if line.strip() != header:
            continue
        cursor = index + 1
        if cursor >= len(lines) or lines[cursor].strip() != "```bash":
            return {}
        cursor += 1

        commands = {}
        while cursor < len(lines):
            current = lines[cursor].strip()
            if current == "```":
                return commands
            if current and ":" in current:
                command_type, command = current.split(":", 1)
                commands[command_type.strip()] = command.strip()
            cursor += 1
        return commands

    return {}


def parse_inline_field(section, title):
    prefix = f"- **{title}**："
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def checksum_map_from_plan(plan_content, known_ids=None):
    allowed_ids = set(known_ids) if known_ids is not None else None
    checksums = {}

    for match in COMPLETED_PATTERN.finditer(plan_content):
        milestone_id, title, completed_at, decisions = match.groups()
        if allowed_ids is not None and milestone_id not in allowed_ids:
            continue
        projection = {
            "status": "completed",
            "title": title.strip(),
            "key_files": [],
            "verify_commands": {},
            "decision_log": [
                item.strip()
                for item in decisions.split(";")
                if item.strip() and item.strip() != "无"
            ],
            "completed_at": completed_at or None,
        }
        checksums[milestone_id] = checksum_for_value(projection)

    sections = re.split(r"(?=###\s+M\d+:)", plan_content)
    for section in sections:
        header_match = MILESTONE_HEADER_PATTERN.match(section.strip())
        if not header_match:
            continue

        milestone_id = header_match.group(1)
        if allowed_ids is not None and milestone_id not in allowed_ids:
            continue
        if milestone_id in checksums:
            continue

        status = "pending"
        status_text = parse_inline_field(section, "状态")
        if status_text is not None:
            for emoji, parsed_status in EMOJI_TO_STATUS.items():
                if emoji in status_text:
                    status = parsed_status
                    break

        completed_at_value = parse_inline_field(section, "完成时间")
        completed_at = completed_at_value or None

        key_files = []
        for item in parse_bullet_section(section, "关键文件"):
            key_files.extend(re.findall(r"`([^`]+)`", item))

        projection = {
            "status": status,
            "key_files": key_files,
            "verify_commands": parse_verify_commands(section),
            "decision_log": parse_bullet_section(section, "决策记录"),
            "completed_at": completed_at,
        }
        checksums[milestone_id] = checksum_for_value(projection)

    return checksums


def export_plan(workflow_dir):
    ms_path = os.path.join(workflow_dir, "milestones.json")
    ms_data, err = load_json(ms_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    revision = ms_data.get("revision", 1)
    milestones = ms_data.get("milestones", [])
    completed = [m for m in milestones if m.get("status") == "completed"]
    active = [m for m in milestones if m.get("status") != "completed"]

    lines = [
        f"<!-- milestones_revision: {revision} -->",
        f"<!-- plan_sync_checksums: {canonical_json(checksum_map_from_milestones(milestones))} -->",
        "",
        "# 实施计划",
        "",
        "> 本文件由 milestones.json 投影生成，作为人工审阅文件。",
        "> 修改后需通过 `python tools/plan_sync.py import` 回写。",
        "",
        "## 架构概览",
        "",
        "```",
        "（架构图）",
        "```",
        "",
        "## 已完成里程碑（折叠区）",
        "",
    ]

    if completed:
        for milestone in completed:
            completed_at = milestone.get("completed_at", "")
            decision_summary = "; ".join(milestone.get("decision_log", [])) or "无"
            lines.append(
                f"✅ {milestone['id']}: {milestone['title']} | "
                f"完成于 {completed_at} | 决策: {decision_summary}"
            )
    else:
        lines.append("<!-- 暂无已完成的里程碑 -->")
    lines.append("")

    lines.extend(["## 当前及待办里程碑", ""])
    if not active:
        lines.append("<!-- 所有里程碑已完成 -->")
    else:
        for milestone in active:
            lines.append(f"### {milestone['id']}: {milestone['title']}")
            lines.append("")
            status_text = STATUS_EMOJI.get(
                milestone.get("status", "pending"), STATUS_EMOJI["pending"]
            )
            lines.append(f"- **状态**：{status_text}")

            acceptance_criteria = milestone.get("acceptance_criteria", [])
            if acceptance_criteria:
                lines.append("- **验收标准**：")
                for criterion in acceptance_criteria:
                    lines.append(f"  - [ ] {criterion}")

            test_design = milestone.get("test_design", [])
            if test_design:
                lines.append("- **测试设计**：")
                for item in test_design:
                    lines.append(f"  - [ ] {item}")

            scope = milestone.get("scope", [])
            if scope:
                lines.append(f"- **范围**：{'; '.join(scope)}")

            key_files = milestone.get("key_files", [])
            if key_files:
                lines.append("- **关键文件**：")
                for file_path in key_files:
                    lines.append(f"  - `{file_path}`")

            verify_commands = milestone.get("verify_commands", {})
            if verify_commands:
                lines.append("- **验证命令**：")
                lines.append("  ```bash")
                for command_type, command in verify_commands.items():
                    if command:
                        lines.append(f"  {command_type}: {command}")
                lines.append("  ```")

            dependencies = milestone.get("dependencies", [])
            if dependencies:
                lines.append(f"- **依赖**：{', '.join(dependencies)}")

            decision_log = milestone.get("decision_log", [])
            lines.append("- **决策记录**：")
            for item in decision_log:
                lines.append(f"  - {item}")

            lines.append(f"- **完成时间**：{milestone.get('completed_at', '')}")
            lines.extend(["", "---", ""])

    lines.extend(
        [
            "## 风险登记表",
            "",
            "| 风险 | 影响 | 概率 | 缓解措施 | 状态 |",
            "|------|------|------|----------|------|",
            "| | | | | |",
            "",
            "## 依赖关系",
            "",
            "```",
        ]
    )

    dependency_lines = []
    for milestone in milestones:
        dependencies = milestone.get("dependencies", [])
        if dependencies:
            dependency_lines.append(f"{', '.join(dependencies)} → {milestone['id']}")
    lines.extend(dependency_lines or ["（无依赖关系）"])
    lines.extend(["```", ""])

    plan_path = os.path.join(workflow_dir, "plan.md")
    with open(plan_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    print(f"EXPORT 完成: milestones.json (rev {revision}) → plan.md")
    return 0


def import_plan(workflow_dir):
    plan_path = os.path.join(workflow_dir, "plan.md")
    ms_path = os.path.join(workflow_dir, "milestones.json")

    if not os.path.exists(plan_path):
        print(f"ERROR: {plan_path} 不存在", file=sys.stderr)
        return 1

    with open(plan_path, "r", encoding="utf-8") as handle:
        plan_content = handle.read()

    revision_match = REVISION_PATTERN.search(plan_content)
    if not revision_match:
        print("ERROR: plan.md 缺少 milestones_revision 元数据", file=sys.stderr)
        return 1

    checksum_metadata, err = parse_checksum_metadata(plan_content)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    plan_revision = int(revision_match.group(1))
    ms_data = None
    if os.path.exists(ms_path):
        ms_data, err = load_json(ms_path)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1

        current_revision = ms_data.get("revision", 0)
        if plan_revision != current_revision:
            print(
                f"CONFLICT: plan.md revision ({plan_revision}) != "
                f"milestones.json revision ({current_revision})",
                file=sys.stderr,
            )
            print("请先运行 export 获取最新版本，再修改", file=sys.stderr)
            return 1

        current_checksums = checksum_map_from_milestones(ms_data.get("milestones", []))
        for milestone_id, expected_checksum in checksum_metadata.items():
            current_checksum = current_checksums.get(milestone_id)
            if current_checksum is not None and current_checksum != expected_checksum:
                print(
                    f"CONFLICT: {milestone_id} 的 checksum 与当前 milestones.json 不一致",
                    file=sys.stderr,
                )
                print("请先运行 export 获取最新版本，再修改", file=sys.stderr)
                return 1

        actual_checksums = checksum_map_from_plan(plan_content, checksum_metadata.keys())
        for milestone_id, actual_checksum in actual_checksums.items():
            if checksum_metadata.get(milestone_id) != actual_checksum:
                print(
                    f"CONFLICT: {milestone_id} 在 plan.md 中的只读投影内容被修改",
                    file=sys.stderr,
                )
                print("只允许编辑标题、依赖、验收标准、测试设计和范围", file=sys.stderr)
                return 1

    milestones = []
    seen_ids = set()

    for match in COMPLETED_PATTERN.finditer(plan_content):
        milestone_id, title, completed_at, _decisions = match.groups()
        seen_ids.add(milestone_id)
        milestones.append(
            {
                "id": milestone_id,
                "title": title.strip(),
                "status": "completed",
            }
        )

    sections = re.split(r"(?=###\s+M\d+:)", plan_content)
    for section in sections:
        header_match = MILESTONE_HEADER_PATTERN.match(section.strip())
        if not header_match:
            continue

        milestone_id = header_match.group(1)
        if milestone_id in seen_ids:
            continue

        milestone = {
            "id": milestone_id,
            "title": header_match.group(2).strip(),
            "status": "pending",
        }

        acceptance_criteria = parse_checkbox_section(section, "验收标准")
        if acceptance_criteria:
            milestone["acceptance_criteria"] = acceptance_criteria

        test_design = parse_checkbox_section(section, "测试设计")
        if test_design:
            milestone["test_design"] = test_design

        scope_match = re.search(r"\*\*范围\*\*[：:]\s*(.+)", section)
        if scope_match:
            milestone["scope"] = [
                item.strip()
                for item in scope_match.group(1).split(";")
                if item.strip()
            ]

        dependency_match = re.search(r"\*\*依赖\*\*[：:]\s*(.+)", section)
        if dependency_match:
            milestone["dependencies"] = re.findall(r"M\d+", dependency_match.group(1))

        seen_ids.add(milestone_id)
        milestones.append(milestone)

    if not milestones:
        print("ERROR: plan.md 中未找到任何里程碑", file=sys.stderr)
        return 1

    errors = []
    parsed_ids = set()
    for milestone in milestones:
        milestone_id = milestone["id"]
        if not re.match(r"^M\d+$", milestone_id):
            errors.append(f"里程碑 ID 格式无效: {milestone_id}")
        if milestone_id in parsed_ids:
            errors.append(f"里程碑 ID 重复: {milestone_id}")
        parsed_ids.add(milestone_id)
        if not milestone.get("title"):
            errors.append(f"{milestone_id} 缺少标题")

    if errors:
        print(f"IMPORT FAILED ({len(errors)} 个问题):", file=sys.stderr)
        for index, error in enumerate(errors, 1):
            print(f"  {index}. {error}", file=sys.stderr)
        return 1

    milestones.sort(key=lambda item: int(item["id"][1:]))

    if ms_data:
        existing_map = {milestone["id"]: milestone for milestone in ms_data.get("milestones", [])}
        for milestone in milestones:
            existing = existing_map.get(milestone["id"])
            if not existing:
                continue

            milestone["status"] = existing.get("status", milestone["status"])
            for field in PRESERVED_FIELDS - {"status"}:
                if field in existing:
                    milestone[field] = existing[field]

            if existing.get("status") == "completed":
                milestone["title"] = existing.get("title", milestone["title"])

            for key, value in existing.items():
                if key not in PLAN_EDITABLE_FIELDS and key not in PRESERVED_FIELDS and key not in milestone:
                    milestone[key] = value

    new_revision = plan_revision + 1
    save_json(ms_path, {"revision": new_revision, "milestones": milestones})

    export_result = export_plan(workflow_dir)
    if export_result != 0:
        print("ERROR: milestones.json 已更新，但 plan.md 回写失败", file=sys.stderr)
        return 1

    print(f"IMPORT 完成: plan.md → milestones.json (rev {new_revision})")
    print(f"  导入了 {len(milestones)} 个里程碑")
    return 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="plan.md 与 milestones.json 同步")
    parser.add_argument(
        "command", choices=["export", "import"], help="export: JSON→MD, import: MD→JSON"
    )
    parser.add_argument("--workflow-dir", default=".workflow", help="工作流目录路径")
    args = parser.parse_args()

    if args.command == "export":
        sys.exit(export_plan(args.workflow_dir))
    sys.exit(import_plan(args.workflow_dir))


if __name__ == "__main__":
    main()
