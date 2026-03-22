#!/usr/bin/env python3
"""PostSkill hook for running workflow_lint after skill execution."""

import json
import os
import subprocess
import sys

_REQUIRED_FILES = ("workflow.json", "milestones.json", "verify.json", "events.jsonl")


def _tools_dir() -> str:
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    plugin_dir = os.path.dirname(hooks_dir)
    return os.path.join(plugin_dir, "tools")


def _find_workflow_dir(cwd: str) -> str | None:
    candidate = os.path.join(cwd, ".workflow")
    if os.path.isdir(candidate):
        return candidate
    return None


def _block_hook_payload_error(message: str) -> None:
    print(f"\n⛔ [auto-pilot] PostSkill hook input parse failed: {message}", file=sys.stderr)
    print("→ Blocking skill completion to avoid skipping workflow lint.", file=sys.stderr)
    sys.exit(2)


def _load_hook_payload():
    raw = sys.stdin.buffer.read()
    if not raw or not raw.strip():
        return None
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        _block_hook_payload_error(f"stdin is not valid UTF-8: {exc}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _block_hook_payload_error(f"stdin is not valid JSON: {exc}")


def main() -> None:
    hook_data = _load_hook_payload() or {}

    cwd = hook_data.get("cwd") or os.getcwd()
    skill_name = hook_data.get("skill_name", "skill")

    workflow_dir = _find_workflow_dir(cwd)
    if not workflow_dir:
        sys.exit(0)

    if not all(os.path.exists(os.path.join(workflow_dir, name)) for name in _REQUIRED_FILES):
        sys.exit(0)

    lint_script = os.path.join(_tools_dir(), "workflow_lint.py")
    if not os.path.exists(lint_script):
        sys.exit(0)

    result = subprocess.run(
        [sys.executable, "-X", "utf8", lint_script, "--workflow-dir", workflow_dir],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    if result.returncode != 0 and result.stderr.strip():
        print(
            f"\n⛔ [auto-pilot] {skill_name} output failed workflow lint and must be fixed:\n"
            f"{result.stderr}",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
