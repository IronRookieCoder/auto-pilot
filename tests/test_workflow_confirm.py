#!/usr/bin/env python3
"""Tests for workflow_confirm.py — confirm_plan lint gate."""

import json
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from plan_sync import export_plan
from workflow_confirm import confirm_plan


class TestConfirmPlanLintGate(unittest.TestCase):
    """确认 plan 前必须通过 lint；warning 不阻断。"""

    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _base_setup(self, verify_commands=None, test_design=None):
        tmpdir = tempfile.mkdtemp()
        self._write_json(
            os.path.join(tmpdir, "workflow.json"),
            {
                "phase": "planning",
                "status": "running",
                "spec_approved": True,
                "plan_approved": False,
                "updated_at": "2026-03-24T10:00:00Z",
                "verify_commands": verify_commands,
            },
        )
        self._write_json(
            os.path.join(tmpdir, "milestones.json"),
            {
                "revision": 1,
                "milestones": [
                    {
                        "id": "M1",
                        "title": "Milestone 1",
                        "status": "pending",
                        "tdd_type": "standard",
                        "acceptance_criteria": ["criterion"],
                        "test_design": test_design or ["test A", "test B"],
                        "test_files": ["tests/test_m1.py"],
                    }
                ],
            },
        )
        with open(os.path.join(tmpdir, "events.jsonl"), "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "time": "2026-03-24T10:00:00Z",
                        "type": "plan_generated",
                        "phase": "planning",
                        "milestone_id": None,
                        "summary": "plan generated",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        self.assertEqual(export_plan(tmpdir), 0)
        return tmpdir

    def test_confirm_plan_rejects_lint_errors_after_import(self):
        tmpdir = self._base_setup(
            verify_commands={"test": "python -m unittest"},
        )
        plan_path = os.path.join(tmpdir, "plan.md")
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()
        plan_content += textwrap.dedent(
            """

            ### M2: Invalid milestone

            - **状态**：🔲 待开始
            - **验收标准**：
              - [ ] another criterion
            - **测试设计**：
              - [ ] another test 1
              - [ ] another test 2
            - **范围**：foo
            - **决策记录**：
            - **完成时间**：
            """
        )
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        self.assertEqual(confirm_plan(tmpdir), 1)

        with open(os.path.join(tmpdir, "workflow.json"), "r", encoding="utf-8") as f:
            workflow = json.load(f)
        self.assertFalse(workflow["plan_approved"])
        self.assertEqual(workflow["phase"], "planning")

    def test_confirm_plan_allows_warnings(self):
        tmpdir = self._base_setup(
            verify_commands={"test": "python -m unittest"},
            test_design=["only one test"],
        )

        self.assertEqual(confirm_plan(tmpdir), 0)

        with open(os.path.join(tmpdir, "workflow.json"), "r", encoding="utf-8") as f:
            workflow = json.load(f)
        self.assertTrue(workflow["plan_approved"])
        self.assertEqual(workflow["phase"], "executing")


if __name__ == "__main__":
    unittest.main()
