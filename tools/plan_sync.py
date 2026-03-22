#!/usr/bin/env python3
"""plan_sync.py - plan.md 与 milestones.json 双向同步

用法：
  python tools/plan_sync.py export [--workflow-dir .workflow]
  python tools/plan_sync.py import [--workflow-dir .workflow]

export: 从 milestones.json 生成 plan.md
import: 解析 plan.md，校验结构，回写 milestones.json
"""

import json
import sys
import os
import re
import hashlib
from datetime import datetime


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


STATUS_EMOJI = {
    "pending": "\U0001f532 待开始",
    "in_progress": "\U0001f536 进行中",
    "completed": "\u2705 已完成",
    "failed": "\u274c 失败",
}

EMOJI_TO_STATUS = {
    "\U0001f532": "pending",
    "\U0001f536": "in_progress",
    "\u2705": "completed",
    "\u274c": "failed",
}


def export_plan(workflow_dir):
    """从 milestones.json 生成 plan.md"""
    ms_path = os.path.join(workflow_dir, "milestones.json")
    ms_data, err = load_json(ms_path)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    revision = ms_data.get("revision", 1)
    milestones = ms_data.get("milestones", [])

    completed = [m for m in milestones if m.get("status") == "completed"]
    active = [m for m in milestones if m.get("status") != "completed"]

    lines = []
    lines.append(f"<!-- milestones_revision: {revision} -->")
    lines.append("")
    lines.append("# 实施计划")
    lines.append("")
    lines.append("> 本文件由 milestones.json 投影生成，作为人工审阅文件。")
    lines.append("> 修改后需通过 `python tools/plan_sync.py import` 回写。")
    lines.append("")

    # 架构概览区（保留占位）
    lines.append("## 架构概览")
    lines.append("")
    lines.append("```")
    lines.append("（架构图）")
    lines.append("```")
    lines.append("")

    # 已完成里程碑
    lines.append("## 已完成里程碑（折叠区）")
    lines.append("")
    if completed:
        for m in completed:
            completed_at = m.get("completed_at", "")
            decision_summary = "; ".join(m.get("decision_log", [])) or "无"
            lines.append(
                f"✅ {m['id']}: {m['title']} | "
                f"完成于 {completed_at} | 决策: {decision_summary}"
            )
    else:
        lines.append("<!-- 暂无已完成的里程碑 -->")
    lines.append("")

    # 当前及待办里程碑
    lines.append("## 当前及待办里程碑")
    lines.append("")
    if not active:
        lines.append("<!-- 所有里程碑已完成 -->")
    else:
        for m in active:
            lines.append(f"### {m['id']}: {m['title']}")
            lines.append("")
            status_text = STATUS_EMOJI.get(m.get("status", "pending"), "\U0001f532 待开始")
            lines.append(f"- **状态**：{status_text}")

            # 验收标准
            ac = m.get("acceptance_criteria", [])
            if ac:
                lines.append("- **验收标准**：")
                for criterion in ac:
                    lines.append(f"  - [ ] {criterion}")

            # 测试设计
            td = m.get("test_design", [])
            if td:
                lines.append("- **测试设计**：")
                for t in td:
                    lines.append(f"  - [ ] {t}")

            # 范围
            scope = m.get("scope", [])
            if scope:
                lines.append(f"- **范围**：{'; '.join(scope)}")

            # 关键文件
            kf = m.get("key_files", [])
            if kf:
                lines.append("- **关键文件**：")
                for f_path in kf:
                    lines.append(f"  - `{f_path}`")

            # 验证命令
            vc = m.get("verify_commands", {})
            if vc:
                lines.append("- **验证命令**：")
                lines.append("  ```bash")
                for vtype, cmd in vc.items():
                    if cmd:
                        lines.append(f"  {vtype}: {cmd}")
                lines.append("  ```")

            # 依赖
            deps = m.get("dependencies", [])
            if deps:
                lines.append(f"- **依赖**：{', '.join(deps)}")

            # 决策记录
            dl = m.get("decision_log", [])
            lines.append("- **决策记录**：")
            if dl:
                for d in dl:
                    lines.append(f"  - {d}")

            # 完成时间
            lines.append(f"- **完成时间**：{m.get('completed_at', '')}")
            lines.append("")
            lines.append("---")
            lines.append("")

    # 风险登记表
    lines.append("## 风险登记表")
    lines.append("")
    lines.append("| 风险 | 影响 | 概率 | 缓解措施 | 状态 |")
    lines.append("|------|------|------|----------|------|")
    lines.append("| | | | | |")
    lines.append("")

    # 依赖关系
    lines.append("## 依赖关系")
    lines.append("")
    lines.append("```")
    dep_lines = []
    for m in milestones:
        deps = m.get("dependencies", [])
        if deps:
            dep_lines.append(f"{', '.join(deps)} → {m['id']}")
    if dep_lines:
        lines.extend(dep_lines)
    else:
        lines.append("（无依赖关系）")
    lines.append("```")
    lines.append("")

    plan_path = os.path.join(workflow_dir, "plan.md")
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"EXPORT 完成: milestones.json (rev {revision}) → plan.md")
    return 0


def import_plan(workflow_dir):
    """解析 plan.md，校验结构，回写 milestones.json"""
    plan_path = os.path.join(workflow_dir, "plan.md")
    ms_path = os.path.join(workflow_dir, "milestones.json")

    if not os.path.exists(plan_path):
        print(f"ERROR: {plan_path} 不存在", file=sys.stderr)
        return 1

    with open(plan_path, "r", encoding="utf-8") as f:
        plan_content = f.read()

    # 检查 revision
    revision_match = re.search(r"<!-- milestones_revision:\s*(\d+)\s*-->", plan_content)
    if not revision_match:
        print("ERROR: plan.md 缺少 milestones_revision 元数据", file=sys.stderr)
        return 1

    plan_rev = int(revision_match.group(1))

    # 检查当前 milestones.json 的 revision
    if os.path.exists(ms_path):
        ms_data, err = load_json(ms_path)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            return 1
        current_rev = ms_data.get("revision", 0)
        if plan_rev != current_rev:
            print(
                f"CONFLICT: plan.md revision ({plan_rev}) != "
                f"milestones.json revision ({current_rev})",
                file=sys.stderr,
            )
            print("请先运行 export 获取最新版本，再修改", file=sys.stderr)
            return 1

    # 解析里程碑
    milestones = []
    errors = []

    # 解析已完成里程碑（折叠行）
    completed_pattern = re.compile(
        r"✅\s+(M\d+):\s+(.+?)\s*\|.*?完成于\s*(\S*)\s*\|.*?决策:\s*(.*)"
    )
    for match in completed_pattern.finditer(plan_content):
        mid, title, completed_at, decisions = match.groups()
        decision_log = [d.strip() for d in decisions.split(";") if d.strip() and d.strip() != "无"]
        milestones.append({
            "id": mid,
            "title": title.strip(),
            "status": "completed",
            "completed_at": completed_at or None,
            "decision_log": decision_log,
        })

    # 解析当前及待办里程碑
    milestone_header_pattern = re.compile(r"###\s+(M\d+):\s+(.+)")
    sections = re.split(r"(?=###\s+M\d+:)", plan_content)

    for section in sections:
        header_match = milestone_header_pattern.match(section.strip())
        if not header_match:
            continue

        mid = header_match.group(1)
        title = header_match.group(2).strip()

        # 跳过已解析的已完成里程碑
        if any(m["id"] == mid for m in milestones):
            continue

        m = {"id": mid, "title": title}

        # 解析状态
        status_match = re.search(r"\*\*状态\*\*[：:]\s*(.*)", section)
        if status_match:
            status_text = status_match.group(1)
            m["status"] = "pending"
            for emoji, status in EMOJI_TO_STATUS.items():
                if emoji in status_text:
                    m["status"] = status
                    break
        else:
            m["status"] = "pending"

        # 解析验收标准
        ac_matches = re.findall(r"- \[[ x]\]\s+(.+)", section)
        # 区分验收标准和测试设计的位置
        ac_section = re.search(
            r"\*\*验收标准\*\*[：:].*?\n((?:\s+- \[[ x]\].+\n)*)", section
        )
        if ac_section:
            m["acceptance_criteria"] = re.findall(
                r"- \[[ x]\]\s+(.+)", ac_section.group(1)
            )

        # 解析测试设计
        td_section = re.search(
            r"\*\*测试设计\*\*[：:].*?\n((?:\s+- \[[ x]\].+\n)*)", section
        )
        if td_section:
            m["test_design"] = re.findall(
                r"- \[[ x]\]\s+(.+)", td_section.group(1)
            )

        # 解析范围
        scope_match = re.search(r"\*\*范围\*\*[：:]\s*(.+)", section)
        if scope_match:
            m["scope"] = [s.strip() for s in scope_match.group(1).split(";") if s.strip()]

        # 解析关键文件
        kf_section = re.search(
            r"\*\*关键文件\*\*[：:].*?\n((?:\s+- .+\n)*)", section
        )
        if kf_section:
            m["key_files"] = re.findall(r"`([^`]+)`", kf_section.group(1))

        # 解析依赖
        dep_match = re.search(r"\*\*依赖\*\*[：:]\s*(.+)", section)
        if dep_match:
            deps_text = dep_match.group(1).strip()
            m["dependencies"] = [
                d.strip() for d in re.findall(r"M\d+", deps_text)
            ]

        milestones.append(m)

    if not milestones:
        print("ERROR: plan.md 中未找到任何里程碑", file=sys.stderr)
        return 1

    # 验证解析结果
    for m in milestones:
        if not re.match(r"^M\d+$", m["id"]):
            errors.append(f"里程碑 ID 格式无效: {m['id']}")
        if not m.get("title"):
            errors.append(f"{m['id']} 缺少标题")

    if errors:
        print(f"IMPORT FAILED ({len(errors)} 个问题):", file=sys.stderr)
        for i, e in enumerate(errors, 1):
            print(f"  {i}. {e}", file=sys.stderr)
        return 1

    # 排序
    milestones.sort(key=lambda m: int(m["id"][1:]))

    # 写入 milestones.json
    new_revision = plan_rev + 1
    output = {"revision": new_revision, "milestones": milestones}
    save_json(ms_path, output)

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
    else:
        sys.exit(import_plan(args.workflow_dir))


if __name__ == "__main__":
    main()
