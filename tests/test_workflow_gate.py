#!/usr/bin/env python3
"""Tests for workflow_gate.py — tdd_type 分支逻辑。"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from workflow_gate import gate_milestone


class TestGateTddTypeBranch(unittest.TestCase):
    """根据 tdd_type 决定 red_evidence 是否必需。"""

    def _setup_workflow_dir(self, milestone, workflow=None, verify=None):
        """创建临时工作流目录并写入测试数据。"""
        tmpdir = tempfile.mkdtemp()
        ms_data = {"revision": 1, "milestones": [milestone]}
        with open(os.path.join(tmpdir, "milestones.json"), "w", encoding="utf-8") as f:
            json.dump(ms_data, f)

        if workflow is None:
            workflow = {
                "phase": "executing",
                "status": "running",
                "plan_approved": True,
                "updated_at": "2026-03-24T10:00:00Z",
            }
        with open(os.path.join(tmpdir, "workflow.json"), "w", encoding="utf-8") as f:
            json.dump(workflow, f)

        if verify is None:
            verify = {
                "revision": 1,
                "runs": [
                    {
                        "id": "run-1",
                        "scope": "milestone",
                        "milestone_id": milestone["id"],
                        "started_at": "2026-03-24T10:00:00Z",
                        "finished_at": "2026-03-24T10:01:00Z",
                        "overall": "pass",
                        "steps": [
                            {
                                "type": "test",
                                "command": "python -m pytest",
                                "exit_code": 0,
                                "started_at": "2026-03-24T10:00:00Z",
                                "finished_at": "2026-03-24T10:01:00Z",
                                "summary": "OK",
                                "passed": True,
                            }
                        ],
                    }
                ],
            }
        with open(os.path.join(tmpdir, "verify.json"), "w", encoding="utf-8") as f:
            json.dump(verify, f)

        return tmpdir

    def test_standard_no_red_evidence_fails_gate(self):
        m = {
            "id": "M1",
            "title": "标准里程碑",
            "status": "in_progress",
            "tdd_type": "standard",
            "test_result": "green",
            "verify_result_summary": "all pass",
            "red_evidence": None,
        }
        tmpdir = self._setup_workflow_dir(m)
        errors = gate_milestone("M1", tmpdir)
        self.assertTrue(
            any("RED 证据" in e for e in errors),
            f"standard 无 red_evidence 应 gate 失败。实际: {errors}",
        )

    def test_setup_no_red_evidence_passes_gate(self):
        m = {
            "id": "M1",
            "title": "Setup 里程碑",
            "status": "in_progress",
            "tdd_type": "setup",
            "test_result": "green",
            "verify_result_summary": "all pass",
            "red_evidence": None,
        }
        tmpdir = self._setup_workflow_dir(m)
        errors = gate_milestone("M1", tmpdir)
        self.assertFalse(
            any("RED 证据" in e for e in errors),
            f"setup 无 red_evidence 不应因 RED 证据 gate 失败。实际: {errors}",
        )

    def test_verification_only_no_red_evidence_passes_gate(self):
        m = {
            "id": "M1",
            "title": "Verify 里程碑",
            "status": "in_progress",
            "tdd_type": "verification_only",
            "test_result": "green",
            "verify_result_summary": "all pass",
            "red_evidence": None,
        }
        tmpdir = self._setup_workflow_dir(m)
        errors = gate_milestone("M1", tmpdir)
        self.assertFalse(
            any("RED 证据" in e for e in errors),
            f"verification_only 无 red_evidence 不应因 RED 证据 gate 失败。实际: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
