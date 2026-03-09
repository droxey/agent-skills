"""
Tests for fix.py – deterministic in-place fixes.
"""

from __future__ import annotations

from pathlib import Path

from skillsctl.audit import run_audit
from skillsctl.fix import (
    _fix_fm001,
    _fix_fm004,
    _fix_fm005,
    _fix_st001,
    run_fix,
)
from skillsctl.plan import run_plan
from skillsctl.rules import BASELINE_RULES, RuleSource

FIXTURES = Path(__file__).parent / "fixtures"


def _rule_source() -> RuleSource:
    return RuleSource(BASELINE_RULES)


def _make_plan(file_path: str) -> dict:
    rs = _rule_source()
    ar = run_audit([file_path], rule_source=rs, dry_run=True)
    return run_plan(ar, dry_run=True)


# ---------------------------------------------------------------------------
# Individual fixers
# ---------------------------------------------------------------------------


class TestFixFM001:
    def test_adds_frontmatter_stub(self) -> None:
        content = "# My Skill\n\nBody text."
        result = _fix_fm001(content, None, content)
        assert result is not None
        assert result.startswith("---\n")
        assert "id:" in result
        assert "name:" in result

    def test_does_not_modify_if_already_has_frontmatter(self) -> None:
        content = "---\nid: x\n---\nBody."
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_fm001(content, fm, body)
        assert result is None

    def test_derives_id_from_heading(self) -> None:
        content = "# My Awesome Skill\n\nDoes things."
        result = _fix_fm001(content, None, content)
        assert "my-awesome-skill" in result

    def test_uses_untitled_when_no_heading(self) -> None:
        content = "No heading here."
        result = _fix_fm001(content, None, content)
        assert result is not None
        assert "untitled-skill" in result or "Untitled" in result


class TestFixFM004:
    def test_normalises_id(self) -> None:
        content = "---\nid: BadID\nname: x\n---\n"
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_fm004(content, fm, body)
        assert result is not None
        assert "badid" in result or "bad-id" in result.lower()

    def test_no_change_if_already_kebab(self) -> None:
        content = "---\nid: good-id\nname: x\n---\n"
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_fm004(content, fm, body)
        assert result is None


class TestFixFM005:
    def test_sets_default_version(self) -> None:
        content = "---\nid: x\nname: y\nversion: v2-invalid\n---\n"
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_fm005(content, fm, body)
        assert result is not None
        assert '"0.1.0"' in result or "'0.1.0'" in result or "0.1.0" in result

    def test_no_change_if_valid_semver(self) -> None:
        content = "---\nid: x\nversion: 2.0.1\n---\n"
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_fm005(content, fm, body)
        assert result is None


class TestFixST001:
    def test_adds_heading(self) -> None:
        content = "---\nid: x\nname: My Skill\n---\n\nBody without heading."
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_st001(content, fm, body)
        assert result is not None
        assert "# My Skill" in result

    def test_no_change_if_heading_exists(self) -> None:
        content = "---\nid: x\nname: My Skill\n---\n\n# My Skill\n\nBody."
        from skillsctl.schema import extract_frontmatter

        fm, body = extract_frontmatter(content)
        result = _fix_st001(content, fm, body)
        assert result is None


# ---------------------------------------------------------------------------
# run_fix (dry-run)
# ---------------------------------------------------------------------------


class TestRunFix:
    def test_dry_run_no_writes(self, tmp_path: Path) -> None:
        src = FIXTURES / "no_frontmatter.md"
        content = src.read_text()
        # Copy to tmp so we can check it's not modified
        target = tmp_path / "no_frontmatter.md"
        target.write_text(content)

        plan = _make_plan(str(target))
        run_fix(plan, apply=False, dry_run=True, rule_source=_rule_source())

        # File should be unchanged in dry-run
        assert target.read_text() == content

    def test_apply_writes_file(self, tmp_path: Path) -> None:
        src = FIXTURES / "no_frontmatter.md"
        target = tmp_path / "no_frontmatter.md"
        target.write_text(src.read_text())

        plan = _make_plan(str(target))
        report = run_fix(plan, apply=True, dry_run=False, rule_source=_rule_source())

        assert report["applied"] is True
        # File should now have frontmatter
        new_content = target.read_text()
        assert new_content.startswith("---")

    def test_report_structure(self, tmp_path: Path) -> None:
        plan = _make_plan(str(FIXTURES / "no_frontmatter.md"))
        report = run_fix(plan, apply=False, dry_run=True, rule_source=_rule_source())
        assert "schema_version" in report
        assert "actions" in report
        assert "applied" in report
        assert "dry_run" in report

    def test_actions_count_matches_fixable(self, tmp_path: Path) -> None:
        src = FIXTURES / "no_frontmatter.md"
        target = tmp_path / "no_frontmatter.md"
        target.write_text(src.read_text())
        plan = _make_plan(str(target))
        fixable = sum(1 for it in plan["items"] if it.get("fixable") and it.get("abs_path"))
        report = run_fix(plan, apply=False, dry_run=True, rule_source=_rule_source())
        assert report["actions_count"] <= fixable
