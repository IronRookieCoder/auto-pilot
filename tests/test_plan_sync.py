#!/usr/bin/env python3
"""Tests for plan_sync.py — 导入新字段回写。"""

import json
import os
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from plan_sync import export_plan, import_plan


class TestPlanSyncImportNewFields(unittest.TestCase):
    """确保 plan.md 中的新字段可导回 milestones.json。"""

    def test_import_parses_tdd_type_and_test_files_for_new_milestone(self):
        tmpdir = tempfile.mkdtemp()
        ms_path = os.path.join(tmpdir, "milestones.json")
        with open(ms_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "revision": 1,
                    "milestones": [
                        {
                            "id": "M1",
                            "title": "Existing milestone",
                            "status": "pending",
                            "tdd_type": "standard",
                            "acceptance_criteria": ["criterion"],
                            "test_design": ["test A", "test B"],
                            "test_files": ["tests/test_existing.py"],
                        }
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        self.assertEqual(export_plan(tmpdir), 0)

        plan_path = os.path.join(tmpdir, "plan.md")
        with open(plan_path, "r", encoding="utf-8") as f:
            plan_content = f.read()
        plan_content += textwrap.dedent(
            """

            ### M2: New milestone

            - **状态**：🔲 待开始
            - **验收标准**：
              - [ ] new criterion
            - **测试设计**：
              - [ ] new test 1
              - [ ] new test 2
            - **范围**：foo; bar
            - **TDD 类型**：standard
            - **测试文件**：
              - `tests/test_new.py`
              - tests/test_other.py
            - **决策记录**：
            - **完成时间**：
            """
        )
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan_content)

        self.assertEqual(import_plan(tmpdir), 0)

        with open(ms_path, "r", encoding="utf-8") as f:
            milestones = json.load(f)["milestones"]

        new_milestone = next(m for m in milestones if m["id"] == "M2")
        self.assertEqual(new_milestone["tdd_type"], "standard")
        self.assertEqual(
            new_milestone["test_files"],
            ["tests/test_new.py", "tests/test_other.py"],
        )


if __name__ == "__main__":
    unittest.main()
