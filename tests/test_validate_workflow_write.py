#!/usr/bin/env python3
"""Tests for validate_workflow_write.py — H2 approved 写保护。"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hooks"))

from validate_workflow_write import _check_approved_protection


class TestApprovedProtection(unittest.TestCase):
    """H2: spec_approved/plan_approved 从非 true 变为 true 时拦截。"""

    def _write_workflow(self, tmpdir, data):
        path = os.path.join(tmpdir, "workflow.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_plan_approved_false_to_true_blocked(self):
        tmpdir = tempfile.mkdtemp()
        path = self._write_workflow(
            tmpdir,
            {
                "phase": "planning",
                "status": "running",
                "updated_at": "2026-03-24T10:00:00Z",
                "plan_approved": False,
            },
        )
        new_data = {
            "phase": "planning",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "plan_approved": True,
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertTrue(
            any("plan_approved" in e for e in errors),
            f"plan_approved false→true 应被拦截。实际: {errors}",
        )

    def test_spec_approved_none_to_true_blocked(self):
        tmpdir = tempfile.mkdtemp()
        path = self._write_workflow(
            tmpdir,
            {
                "phase": "init",
                "status": "running",
                "updated_at": "2026-03-24T10:00:00Z",
            },
        )
        new_data = {
            "phase": "init",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "spec_approved": True,
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertTrue(
            any("spec_approved" in e for e in errors),
            f"spec_approved None→true 应被拦截。实际: {errors}",
        )

    def test_normal_write_not_blocked(self):
        tmpdir = tempfile.mkdtemp()
        path = self._write_workflow(
            tmpdir,
            {
                "phase": "executing",
                "status": "running",
                "updated_at": "2026-03-24T10:00:00Z",
                "plan_approved": True,
                "spec_approved": True,
            },
        )
        new_data = {
            "phase": "executing",
            "status": "running",
            "updated_at": "2026-03-24T11:00:00Z",
            "plan_approved": True,
            "spec_approved": True,
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertEqual(
            errors,
            [],
            f"正常写入不应触发拦截。实际: {errors}",
        )

    def test_approved_true_to_true_not_blocked(self):
        """已是 true 保持 true 不应拦截。"""
        tmpdir = tempfile.mkdtemp()
        path = self._write_workflow(
            tmpdir,
            {
                "phase": "planning",
                "status": "running",
                "updated_at": "2026-03-24T10:00:00Z",
                "plan_approved": True,
            },
        )
        new_data = {
            "phase": "planning",
            "status": "running",
            "updated_at": "2026-03-24T11:00:00Z",
            "plan_approved": True,
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertEqual(
            errors,
            [],
            f"true→true 不应拦截。实际: {errors}",
        )

    def test_new_file_with_approved_true_blocked(self):
        """文件不存在时也不允许直接写 approved=true。"""
        path = os.path.join(tempfile.mkdtemp(), "nonexistent.json")
        new_data = {
            "phase": "init",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "spec_approved": True,
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertTrue(
            any("spec_approved" in e for e in errors),
            f"新文件首次写入 approved=true 应被拦截。实际: {errors}",
        )

    def test_new_file_without_approved_not_blocked(self):
        """首次创建且不改 approved 字段时允许。"""
        path = os.path.join(tempfile.mkdtemp(), "nonexistent.json")
        new_data = {
            "phase": "init",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
        }
        errors = []
        _check_approved_protection(path, new_data, errors)
        self.assertEqual(
            errors,
            [],
            f"新文件不涉及 approved 字段时不应拦截。实际: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
