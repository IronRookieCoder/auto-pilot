#!/usr/bin/env python3
"""Tests for workflow_lint.py — TDD 强化校验逻辑。"""

import os
import sys
import unittest

# 确保 tools/ 在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from workflow_lint import validate_milestones, check_plan_tdd_readiness


def _make_milestones_data(milestones_list):
    return {"revision": 1, "milestones": milestones_list}


def _base_milestone(**overrides):
    m = {
        "id": "M1",
        "title": "测试里程碑",
        "status": "pending",
        "tdd_type": "standard",
        "test_design": ["测试A", "测试B"],
        "acceptance_criteria": ["验收标准1"],
        "test_files": ["tests/test_foo.py"],
    }
    m.update(overrides)
    return m


class TestH1_TestDesignNonEmpty(unittest.TestCase):
    """H1: test_design 为空/缺失时 lint 报错。"""

    def test_empty_test_design_error(self):
        data = _make_milestones_data([_base_milestone(test_design=[])])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("test_design 不能为空数组" in e for e in errors),
            f"应检测到 test_design 为空数组。实际错误: {errors}",
        )

    def test_nonempty_test_design_ok(self):
        data = _make_milestones_data([_base_milestone(test_design=["测试A"])])
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("test_design 不能为空数组" in e for e in errors),
            f"非空 test_design 不应报错。实际错误: {errors}",
        )


class TestH1_AcceptanceCriteriaNonEmpty(unittest.TestCase):
    """H1: acceptance_criteria 为空/缺失时 lint 报错。"""

    def test_empty_acceptance_criteria_error(self):
        data = _make_milestones_data([_base_milestone(acceptance_criteria=[])])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("acceptance_criteria 不能为空数组" in e for e in errors),
            f"应检测到 acceptance_criteria 为空数组。实际错误: {errors}",
        )

    def test_nonempty_acceptance_criteria_ok(self):
        data = _make_milestones_data([_base_milestone(acceptance_criteria=["标准1"])])
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("acceptance_criteria 不能为空数组" in e for e in errors),
            f"非空 acceptance_criteria 不应报错。实际错误: {errors}",
        )


class TestF1_TddType(unittest.TestCase):
    """F1: tdd_type 无效值/缺失时 lint 报错。"""

    def test_missing_tdd_type_error(self):
        """tdd_type 是 required 字段，缺失时 lint 报错。"""
        m = _base_milestone()
        del m["tdd_type"]
        data = _make_milestones_data([m])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("缺少必需字段: tdd_type" in e for e in errors),
            f"缺少 tdd_type 应报缺少必需字段。实际错误: {errors}",
        )

    def test_invalid_tdd_type_error(self):
        data = _make_milestones_data([_base_milestone(tdd_type="invalid_type")])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("tdd_type 无效" in e for e in errors),
            f"应检测到无效 tdd_type。实际错误: {errors}",
        )

    def test_valid_tdd_type_standard_ok(self):
        data = _make_milestones_data([_base_milestone(tdd_type="standard")])
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("tdd_type" in e for e in errors),
            f"合法 tdd_type=standard 不应报错。实际错误: {errors}",
        )

    def test_valid_tdd_type_setup_ok(self):
        data = _make_milestones_data([_base_milestone(tdd_type="setup", test_files=[])])
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("tdd_type 无效" in e for e in errors),
            f"合法 tdd_type=setup 不应报错。实际错误: {errors}",
        )

    def test_valid_tdd_type_verification_only_ok(self):
        data = _make_milestones_data(
            [_base_milestone(tdd_type="verification_only", test_files=[])]
        )
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("tdd_type 无效" in e for e in errors),
            f"合法 tdd_type=verification_only 不应报错。实际错误: {errors}",
        )


class TestF2_TestFiles(unittest.TestCase):
    """F2: test_files 非字符串数组时 lint 报错。"""

    def test_non_array_test_files_error(self):
        data = _make_milestones_data([_base_milestone(test_files="not_a_list")])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("test_files 必须是字符串数组" in e for e in errors),
            f"非数组 test_files 应报错。实际错误: {errors}",
        )

    def test_non_string_items_error(self):
        data = _make_milestones_data([_base_milestone(test_files=[123, True])])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("test_files 必须是字符串数组" in e for e in errors),
            f"含非字符串元素应报错。实际错误: {errors}",
        )

    def test_standard_empty_test_files_error(self):
        """tdd_type=standard 时 test_files 不能为空。"""
        data = _make_milestones_data([_base_milestone(tdd_type="standard", test_files=[])])
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("tdd_type=standard 时 test_files 不能为空" in e for e in errors),
            f"standard 类型空 test_files 应报错。实际错误: {errors}",
        )


class TestCompletedRedEvidence(unittest.TestCase):
    """completed 状态时根据 tdd_type 决定 red_evidence 是否必需。"""

    def _completed_milestone(self, **overrides):
        m = {
            "id": "M1",
            "title": "已完成里程碑",
            "status": "completed",
            "tdd_type": "standard",
            "test_design": ["测试A", "测试B"],
            "acceptance_criteria": ["标准1"],
            "test_files": ["tests/test_foo.py"],
            "red_evidence": "测试失败输出",
            "test_result": "green",
            "completed_at": "2026-03-24T10:00:00Z",
        }
        m.update(overrides)
        return m

    def test_standard_completed_without_red_evidence_error(self):
        data = _make_milestones_data(
            [self._completed_milestone(tdd_type="standard", red_evidence=None)]
        )
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("red_evidence 不能为 null" in e for e in errors),
            f"standard+completed 无 red_evidence 应报错。实际错误: {errors}",
        )

    def test_setup_completed_without_red_evidence_ok(self):
        data = _make_milestones_data(
            [self._completed_milestone(tdd_type="setup", red_evidence=None, test_files=[])]
        )
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("red_evidence 不能为 null" in e for e in errors),
            f"setup+completed 无 red_evidence 不应报错。实际错误: {errors}",
        )

    def test_verification_only_completed_without_red_evidence_ok(self):
        data = _make_milestones_data(
            [
                self._completed_milestone(
                    tdd_type="verification_only", red_evidence=None, test_files=[]
                )
            ]
        )
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("red_evidence 不能为 null" in e for e in errors),
            f"verification_only+completed 无 red_evidence 不应报错。实际错误: {errors}",
        )


class TestH3_PlanTddReadiness(unittest.TestCase):
    """H3: test_design < 2 条时 warn; 无测试命令且无 M0 时报错。"""

    def test_short_test_design_warn(self):
        milestones = _make_milestones_data(
            [_base_milestone(id="M1", test_design=["仅一条"])]
        )
        workflow = {
            "phase": "planning",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "verify_commands": {"test": "python -m unittest"},
        }
        errors = []
        warnings = []
        check_plan_tdd_readiness(workflow, milestones, errors, warnings)
        self.assertEqual(errors, [], f"test_design 仅 1 条不应作为错误。实际错误: {errors}")
        self.assertTrue(
            any("test_design 少于 2 条" in e for e in warnings),
            f"test_design 仅 1 条应警告。实际警告: {warnings}",
        )

    def test_no_test_command_no_m0_error(self):
        milestones = _make_milestones_data([_base_milestone(id="M1")])
        workflow = {
            "phase": "executing",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "verify_commands": {"test": None},
        }
        errors = []
        check_plan_tdd_readiness(workflow, milestones, errors)
        self.assertTrue(
            any("无测试命令" in e for e in errors),
            f"无测试命令且无 M0 应报错。实际错误: {errors}",
        )

    def test_has_m0_no_test_command_ok(self):
        milestones = _make_milestones_data(
            [
                _base_milestone(id="M0", test_design=["搭建测试环境"]),
                _base_milestone(id="M1"),
            ]
        )
        workflow = {
            "phase": "executing",
            "status": "running",
            "updated_at": "2026-03-24T10:00:00Z",
            "verify_commands": {"test": None},
        }
        errors = []
        check_plan_tdd_readiness(workflow, milestones, errors)
        self.assertFalse(
            any("无测试命令" in e for e in errors),
            f"有 M0 时不应报无测试命令错误。实际错误: {errors}",
        )


class TestNormalDataPassesLint(unittest.TestCase):
    """正常数据通过 lint 无报错。"""

    def test_valid_data_no_errors(self):
        data = _make_milestones_data([_base_milestone()])
        errors = []
        validate_milestones(data, errors)
        self.assertEqual(errors, [], f"合法数据不应有错误。实际: {errors}")


if __name__ == "__main__":
    unittest.main()
