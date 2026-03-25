#!/usr/bin/env python3
"""Tests for workflow_resume.py."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from workflow_resume import resume_workflow


class TestWorkflowResume(unittest.TestCase):
    def _write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def _base_workflow_dir(self, workflow, milestones):
        tmpdir = tempfile.mkdtemp()
        self._write_json(os.path.join(tmpdir, "workflow.json"), workflow)
        self._write_json(
            os.path.join(tmpdir, "milestones.json"),
            {"revision": 1, "milestones": milestones},
        )
        self._write_json(os.path.join(tmpdir, "verify.json"), {"revision": 1, "runs": []})
        with open(os.path.join(tmpdir, "events.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "time": "2026-03-25T10:00:00Z",
                        "type": "workflow_blocked",
                        "phase": workflow["phase"],
                        "milestone_id": workflow.get("current_milestone_id"),
                        "summary": "workflow blocked",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return tmpdir

    def test_resume_failed_executing_workflow(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "executing",
                "status": "failed",
                "reason": "M1 验证失败",
                "spec_approved": True,
                "plan_approved": True,
                "current_milestone_id": "M1",
                "verify_commands": {"test": "python -m unittest"},
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [
                {
                    "id": "M1",
                    "title": "核心里程碑",
                    "status": "failed",
                    "tdd_type": "standard",
                    "test_design": ["测试A", "测试B"],
                    "acceptance_criteria": ["标准1"],
                    "test_files": ["tests/test_m1.py"],
                }
            ],
        )

        self.assertEqual(resume_workflow(tmpdir), 0)

        with open(os.path.join(tmpdir, "workflow.json"), "r", encoding="utf-8") as handle:
            workflow = json.load(handle)
        self.assertEqual(workflow["status"], "running")
        self.assertNotIn("reason", workflow)

        with open(os.path.join(tmpdir, "events.jsonl"), "r", encoding="utf-8") as handle:
            events = [json.loads(line) for line in handle if line.strip()]
        self.assertEqual(events[-1]["type"], "workflow_resumed")
        self.assertEqual(events[-1]["artifacts"]["previous_status"], "failed")

    def test_resume_rejects_non_resumable_status(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "planning",
                "status": "running",
                "spec_approved": True,
                "plan_approved": False,
                "current_milestone_id": None,
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [],
        )

        self.assertEqual(resume_workflow(tmpdir), 1)

    def test_resume_rejects_lint_failure(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "planning",
                "status": "blocked",
                "reason": "等待确认",
                "spec_approved": False,
                "plan_approved": False,
                "current_milestone_id": None,
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [],
        )

        self.assertEqual(resume_workflow(tmpdir), 1)

    def test_resume_rejects_verifying_with_open_milestones(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "verifying",
                "status": "paused",
                "reason": "等待重试",
                "spec_approved": True,
                "plan_approved": True,
                "current_milestone_id": None,
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [
                {
                    "id": "M1",
                    "title": "未完成里程碑",
                    "status": "pending",
                    "tdd_type": "standard",
                    "test_design": ["测试A", "测试B"],
                    "acceptance_criteria": ["标准1"],
                    "test_files": ["tests/test_m1.py"],
                }
            ],
        )

        self.assertEqual(resume_workflow(tmpdir), 1)

    def test_resume_rejects_failed_milestone_without_current_pointer(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "executing",
                "status": "failed",
                "reason": "M1 失败",
                "spec_approved": True,
                "plan_approved": True,
                "current_milestone_id": None,
                "verify_commands": {"test": "python -m unittest"},
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [
                {
                    "id": "M1",
                    "title": "失败里程碑",
                    "status": "failed",
                    "tdd_type": "standard",
                    "test_design": ["测试A", "测试B"],
                    "acceptance_criteria": ["标准1"],
                    "test_files": ["tests/test_m1.py"],
                },
                {
                    "id": "M2",
                    "title": "待执行里程碑",
                    "status": "pending",
                    "tdd_type": "standard",
                    "test_design": ["测试C", "测试D"],
                    "acceptance_criteria": ["标准2"],
                    "test_files": ["tests/test_m2.py"],
                },
            ],
        )

        self.assertEqual(resume_workflow(tmpdir), 1)

    def test_resume_rejects_when_current_pointer_skips_failed_milestone(self):
        tmpdir = self._base_workflow_dir(
            {
                "phase": "executing",
                "status": "paused",
                "reason": "准备恢复",
                "spec_approved": True,
                "plan_approved": True,
                "current_milestone_id": "M2",
                "verify_commands": {"test": "python -m unittest"},
                "updated_at": "2026-03-25T10:00:00Z",
            },
            [
                {
                    "id": "M1",
                    "title": "失败里程碑",
                    "status": "failed",
                    "tdd_type": "standard",
                    "test_design": ["测试A", "测试B"],
                    "acceptance_criteria": ["标准1"],
                    "test_files": ["tests/test_m1.py"],
                },
                {
                    "id": "M2",
                    "title": "错误恢复目标",
                    "status": "pending",
                    "tdd_type": "standard",
                    "test_design": ["测试C", "测试D"],
                    "acceptance_criteria": ["标准2"],
                    "test_files": ["tests/test_m2.py"],
                },
            ],
        )

        self.assertEqual(resume_workflow(tmpdir), 1)


if __name__ == "__main__":
    unittest.main()
