"""
Tests for plan.py – prioritisation and plan generation.
"""

from __future__ import annotations

from pathlib import Path

from skillsctl.audit import run_audit
from skillsctl.plan import run_plan
from skillsctl.rules import BASELINE_RULES, RuleSource

FIXTURES = Path(__file__).parent / "fixtures"


def _make_audit_report(file_path: str) -> dict:
    rs = RuleSource(BASELINE_RULES)
    return run_audit([file_path], rule_source=rs, dry_run=True)


# ---------------------------------------------------------------------------
# run_plan
# ---------------------------------------------------------------------------


class TestRunPlan:
    def test_plan_from_audit(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        assert plan["summary"]["total_items"] > 0

    def test_items_have_rank(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "bad_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        for item in plan["items"]:
            assert "rank" in item
            assert isinstance(item["rank"], int)

    def test_items_ranked_consecutively(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        ranks = [it["rank"] for it in plan["items"]]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_errors_ranked_before_warnings(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "bad_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        items = plan["items"]
        # Find index of first warning vs first error
        severities = [it["severity"] for it in items]
        if "error" in severities and "warning" in severities:
            assert severities.index("error") < severities.index("warning")

    def test_fixable_count(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        s = plan["summary"]
        manual_count = sum(1 for it in plan["items"] if it.get("fixable"))
        assert s["fixable_items"] == manual_count

    def test_plan_has_action_field(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "missing_fields.md"))
        plan = run_plan(ar, dry_run=True)
        for item in plan["items"]:
            assert "action" in item
            assert isinstance(item["action"], str)
            assert len(item["action"]) > 0

    def test_plan_has_risk_field(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        for item in plan["items"]:
            assert item["risk"] in {"low", "medium", "high"}

    def test_json_output(self, tmp_path: Path) -> None:
        import json

        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        out = tmp_path / "plan.json"
        run_plan(ar, output_path=str(out), dry_run=True)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "items" in data

    def test_markdown_output(self, tmp_path: Path) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        out_md = tmp_path / "plan.md"
        run_plan(ar, report_md_path=str(out_md), dry_run=True)
        assert out_md.exists()
        md = out_md.read_text()
        assert "# Improvement Plan" in md
        assert "| # |" in md

    def test_empty_audit_produces_empty_plan(self) -> None:
        ar = {"files": [], "rule_source": {}}
        plan = run_plan(ar, dry_run=True)
        assert plan["summary"]["total_items"] == 0
        assert plan["items"] == []

    def test_plan_structure(self) -> None:
        ar = _make_audit_report(str(FIXTURES / "no_frontmatter.md"))
        plan = run_plan(ar, dry_run=True)
        assert "schema_version" in plan
        assert "created_at" in plan
        assert "summary" in plan
        assert "items" in plan
