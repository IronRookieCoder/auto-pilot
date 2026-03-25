#!/usr/bin/env python3
"""Tests for spec-plan consistency check in workflow_lint.py."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from workflow_lint import check_spec_plan_consistency, parse_spec_ids


SPEC_WITH_IDS = """\
## 功能需求

1. [FR-1] 用户可以创建任务
2. [FR-2] 用户可以删除任务

## 范围边界

### 在范围内
- [IN-1] 支持任务增删改查

### 不在范围内
- [OUT-1] 不实现多人协作

## 验收标准

1. [AC-1] 空标题提交时提示错误
2. [AC-2] 删除后列表不再显示该任务
"""


def _write_files(tmpdir, spec_content, milestones):
    spec_path = os.path.join(tmpdir, "spec.md")
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(spec_content)
    ms_path = os.path.join(tmpdir, "milestones.json")
    with open(ms_path, "w", encoding="utf-8") as f:
        json.dump({"revision": 1, "milestones": milestones}, f, ensure_ascii=False)


def _milestone(mid, spec_refs, **overrides):
    m = {
        "id": mid,
        "title": f"里程碑 {mid}",
        "status": "pending",
        "tdd_type": "standard",
        "test_design": ["测试A", "测试B"],
        "acceptance_criteria": ["标准1"],
        "test_files": ["tests/test.py"],
        "spec_refs": spec_refs,
    }
    m.update(overrides)
    return m


class TestParseSpecIds(unittest.TestCase):
    """测试 spec.md 中的追踪 ID 解析。"""

    def test_parse_all_id_types(self):
        ids_by_prefix, all_ids = parse_spec_ids(SPEC_WITH_IDS)
        self.assertEqual(ids_by_prefix["FR"], {"FR-1", "FR-2"})
        self.assertEqual(ids_by_prefix["IN"], {"IN-1"})
        self.assertEqual(ids_by_prefix["OUT"], {"OUT-1"})
        self.assertEqual(ids_by_prefix["AC"], {"AC-1", "AC-2"})
        self.assertEqual(all_ids, {"FR-1", "FR-2", "IN-1", "OUT-1", "AC-1", "AC-2"})

    def test_no_ids_returns_empty(self):
        ids_by_prefix, all_ids = parse_spec_ids("## 功能需求\n\n1. 普通文本")
        self.assertEqual(all_ids, set())


class TestSpecPlanConsistency(unittest.TestCase):
    """测试 spec-plan 一致性检查。"""

    def test_full_coverage_no_errors(self):
        """所有 spec 条目被完整覆盖时无错误。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "IN-1", "AC-1"]),
                _milestone("M2", ["FR-2", "AC-2"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertEqual(errors, [], f"完整覆盖不应有错误: {errors}")

    def test_missing_spec_refs_error(self):
        """里程碑缺少 spec_refs 时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "IN-1", "AC-1", "AC-2"]),
                _milestone("M2", None),
            ]
            milestones[1]["spec_refs"] = None
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("milestones[M2] 缺少 spec_refs" in e for e in errors),
                f"缺少 spec_refs 应报错: {errors}",
            )

    def test_empty_spec_refs_error(self):
        """里程碑 spec_refs 为空数组时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "IN-1", "AC-1", "AC-2"]),
                _milestone("M2", []),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("milestones[M2] 缺少 spec_refs" in e for e in errors),
                f"空 spec_refs 应报错: {errors}",
            )

    def test_nonexistent_ref_error(self):
        """引用了 spec 中不存在的 ID 时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "FR-99", "IN-1", "AC-1", "AC-2"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("引用了不存在的 spec 条目 FR-99" in e for e in errors),
                f"引用不存在 ID 应报错: {errors}",
            )

    def test_out_ref_error(self):
        """引用 OUT-* 条目时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "IN-1", "AC-1", "AC-2", "OUT-1"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("引用了 OUT-1" in e for e in errors),
                f"引用 OUT-* 应报错: {errors}",
            )

    def test_uncovered_ac_error(self):
        """验收标准 AC-* 未被覆盖时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "IN-1", "AC-1"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("AC-2 未被任何 milestone 覆盖" in e for e in errors),
                f"未覆盖 AC-2 应报错: {errors}",
            )

    def test_uncovered_in_error(self):
        """范围内条目 IN-* 未被覆盖时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "AC-1", "AC-2"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("IN-1 未被任何 milestone 覆盖" in e for e in errors),
                f"未覆盖 IN-1 应报错: {errors}",
            )

    def test_uncovered_fr_error(self):
        """功能需求 FR-* 未被覆盖时报错（严格模式）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "IN-1", "AC-1", "AC-2"]),
            ]
            _write_files(tmpdir, SPEC_WITH_IDS, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("FR-2 未被任何 milestone 覆盖" in e for e in errors),
                f"未覆盖 FR-2 应报错: {errors}",
            )

    def test_no_spec_ids_error(self):
        """spec.md 中没有追踪 ID 时报错。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            spec_no_ids = "## 功能需求\n\n1. 普通文本\n"
            milestones = [_milestone("M1", ["FR-1"])]
            _write_files(tmpdir, spec_no_ids, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("未找到任何追踪 ID" in e for e in errors),
                f"无追踪 ID 应报错: {errors}",
            )

    def test_no_spec_file_skips(self):
        """spec.md 不存在时跳过检查。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ms_data = {"revision": 1, "milestones": [_milestone("M1", ["FR-1"])]}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertEqual(errors, [])

    def test_too_many_refs_warning(self):
        """单个里程碑引用过多条目时警告。"""
        spec_many = "## 功能需求\n\n"
        refs = []
        for i in range(1, 12):
            spec_many += f"{i}. [FR-{i}] 功能{i}\n"
            refs.append(f"FR-{i}")
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [_milestone("M1", refs)]
            _write_files(tmpdir, spec_many, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("spec_refs 数量为" in w for w in warnings),
                f"过多 refs 应警告: {warnings}",
            )

    def test_ac_concentration_warning(self):
        """大多数 AC 集中在一个里程碑时警告。"""
        spec = """\
## 功能需求
1. [FR-1] 功能1
2. [FR-2] 功能2

## 范围边界
### 在范围内
- [IN-1] 范围1

## 验收标准
1. [AC-1] 标准1
2. [AC-2] 标准2
3. [AC-3] 标准3
4. [AC-4] 标准4
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            milestones = [
                _milestone("M1", ["FR-1", "FR-2", "IN-1", "AC-1", "AC-2", "AC-3", "AC-4"]),
            ]
            _write_files(tmpdir, spec, milestones)
            ms_data = {"revision": 1, "milestones": milestones}
            errors, warnings = [], []
            check_spec_plan_consistency(tmpdir, ms_data, errors, warnings)
            self.assertTrue(
                any("集中了" in w for w in warnings),
                f"AC 集中应警告: {warnings}",
            )


class TestSpecRefsValidation(unittest.TestCase):
    """测试 validate_milestones 中的 spec_refs 类型校验。"""

    def test_spec_refs_not_array_error(self):
        from workflow_lint import validate_milestones

        m = {
            "id": "M1", "title": "T", "status": "pending", "tdd_type": "standard",
            "test_design": ["A", "B"], "acceptance_criteria": ["C"],
            "test_files": ["t.py"], "spec_refs": "not-an-array",
        }
        data = {"revision": 1, "milestones": [m]}
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("spec_refs 必须是字符串数组" in e for e in errors),
            f"非数组 spec_refs 应报错: {errors}",
        )

    def test_spec_refs_invalid_id_format_error(self):
        from workflow_lint import validate_milestones

        m = {
            "id": "M1", "title": "T", "status": "pending", "tdd_type": "standard",
            "test_design": ["A", "B"], "acceptance_criteria": ["C"],
            "test_files": ["t.py"], "spec_refs": ["INVALID-1"],
        }
        data = {"revision": 1, "milestones": [m]}
        errors = []
        validate_milestones(data, errors)
        self.assertTrue(
            any("spec_refs 包含无效 ID: INVALID-1" in e for e in errors),
            f"无效 ID 格式应报错: {errors}",
        )

    def test_spec_refs_valid_ok(self):
        from workflow_lint import validate_milestones

        m = {
            "id": "M1", "title": "T", "status": "pending", "tdd_type": "standard",
            "test_design": ["A", "B"], "acceptance_criteria": ["C"],
            "test_files": ["t.py"], "spec_refs": ["FR-1", "AC-2", "IN-3"],
        }
        data = {"revision": 1, "milestones": [m]}
        errors = []
        validate_milestones(data, errors)
        self.assertFalse(
            any("spec_refs" in e for e in errors),
            f"合法 spec_refs 不应报错: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
