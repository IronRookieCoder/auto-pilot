#!/usr/bin/env python3
"""Initialize .workflow state files from the JSON schemas."""

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone


def _tools_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _schema_path(filename: str) -> str:
    return os.path.join(_tools_dir(), "schemas", filename)


def _load_schema(filename: str) -> dict:
    path = _schema_path(filename)
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_schema(schema: dict, root: dict) -> dict:
    current = schema
    while "$ref" in current:
        ref = current["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"Unsupported schema ref: {ref}")
        node = root
        for part in ref[2:].split("/"):
            node = node[part]
        current = node
    return current


def _pick_type(schema: dict) -> str | None:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        if non_null:
            return non_null[0]
        return "null"
    return schema_type


def _default_from_schema(schema: dict, root: dict):
    resolved = _resolve_schema(schema, root)

    if "const" in resolved:
        return copy.deepcopy(resolved["const"])
    if "default" in resolved:
        return copy.deepcopy(resolved["default"])
    if "enum" in resolved:
        for item in resolved["enum"]:
            if item is not None:
                return copy.deepcopy(item)
        return None

    schema_type = _pick_type(resolved)
    if schema_type == "object":
        result = {}
        properties = resolved.get("properties", {})
        for key in resolved.get("required", []):
            if key in properties:
                result[key] = _default_from_schema(properties[key], root)
        return result
    if schema_type == "array":
        return []
    if schema_type == "integer":
        return resolved.get("minimum", 0)
    if schema_type == "number":
        return resolved.get("minimum", 0)
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        return ""
    if schema_type == "null":
        return None
    return None


def _build_schema_object(schema: dict, values: dict | None = None) -> dict:
    values = values or {}
    resolved = _resolve_schema(schema, schema)
    properties = resolved.get("properties", {})
    result = _default_from_schema(resolved, schema)

    for key, value in values.items():
        if key not in properties:
            raise KeyError(f"Schema does not define field: {key}")
        result[key] = value

    return result


def _initial_workflow(verify_cmds: dict) -> dict:
    schema = _load_schema("workflow.schema.json")
    verify_schema = schema["properties"]["verify_commands"]
    verify_commands = _build_schema_object(
        verify_schema,
        {
            "lint": verify_cmds.get("lint"),
            "typecheck": verify_cmds.get("typecheck"),
            "test": verify_cmds.get("test"),
            "build": verify_cmds.get("build"),
        },
    )
    return _build_schema_object(
        schema,
        {
            "phase": "init",
            "status": "running",
            "current_milestone_id": None,
            "spec_approved": False,
            "plan_approved": False,
            "verify_commands": verify_commands,
            "final_verify_overall": None,
            "updated_at": _now_iso(),
        },
    )


def _initial_milestones() -> dict:
    schema = _load_schema("milestones.schema.json")
    return _build_schema_object(schema)


def _initial_verify() -> dict:
    schema = _load_schema("verify.schema.json")
    return _build_schema_object(schema)


def _initial_event() -> str:
    schema = _load_schema("event.schema.json")
    event = _build_schema_object(
        schema,
        {
            "time": _now_iso(),
            "type": "workflow_init",
            "phase": "init",
            "milestone_id": None,
            "summary": "Workflow initialized",
            "artifacts": None,
        },
    )
    return json.dumps(event, ensure_ascii=False)


def _write_if_absent(path: str, content: str, label: str) -> bool:
    if os.path.exists(path):
        print(f"  skipped: {label} already exists")
        return False
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    print(f"  created: {label}")
    return True


def init_workflow(workflow_dir: str, verify_cmds: dict) -> int:
    try:
        os.makedirs(workflow_dir, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: failed to create {workflow_dir}: {exc}", file=sys.stderr)
        return 1

    print(f"Initializing workflow directory: {os.path.abspath(workflow_dir)}")

    files = [
        (
            os.path.join(workflow_dir, "workflow.json"),
            json.dumps(_initial_workflow(verify_cmds), ensure_ascii=False, indent=2)
            + "\n",
            "workflow.json",
        ),
        (
            os.path.join(workflow_dir, "milestones.json"),
            json.dumps(_initial_milestones(), ensure_ascii=False, indent=2) + "\n",
            "milestones.json",
        ),
        (
            os.path.join(workflow_dir, "verify.json"),
            json.dumps(_initial_verify(), ensure_ascii=False, indent=2) + "\n",
            "verify.json",
        ),
        (
            os.path.join(workflow_dir, "events.jsonl"),
            _initial_event() + "\n",
            "events.jsonl",
        ),
    ]

    try:
        for path, content, label in files:
            _write_if_absent(path, content, label)
    except OSError as exc:
        print(f"ERROR: failed to write workflow files: {exc}", file=sys.stderr)
        return 1

    print("Workflow state files are ready.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Initialize workflow files from the JSON schemas."
    )
    parser.add_argument(
        "--workflow-dir",
        default=".workflow",
        help="Workflow directory path (default: .workflow)",
    )
    parser.add_argument("--verify-lint", default=None, help="lint command")
    parser.add_argument("--verify-typecheck", default=None, help="typecheck command")
    parser.add_argument("--verify-test", default=None, help="test command")
    parser.add_argument("--verify-build", default=None, help="build command")
    args = parser.parse_args()

    verify_cmds = {
        "lint": args.verify_lint,
        "typecheck": args.verify_typecheck,
        "test": args.verify_test,
        "build": args.verify_build,
    }

    sys.exit(init_workflow(args.workflow_dir, verify_cmds))


if __name__ == "__main__":
    main()
