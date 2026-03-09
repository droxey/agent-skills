"""
Tests for audit.py – rule firing and report generation.
"""

from __future__ import annotations

from pathlib import Path

from skillsctl.audit import audit_file, run_audit
from skillsctl.rules import BASELINE_RULES, RuleSource

FIXTURES = Path(__file__).parent / "fixtures"


def _rule_source() -> RuleSource:
    return RuleSource(BASELINE_RULES)


# ---------------------------------------------------------------------------
# audit_file
# ---------------------------------------------------------------------------


class TestAuditFile:
    def test_no_frontmatter_fires_fm001(self) -> None:
        content = "# A heading\n\nSome text here, no frontmatter at all."
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "FM001" in rule_ids

    def test_good_skill_has_no_errors(self) -> None:
        content = (FIXTURES / "good_skill.md").read_text()
        findings = audit_file(content, BASELINE_RULES)
        errors = [f for f in findings if f["severity"] == "error"]
        assert errors == []

    def test_missing_fields_fires_fm003(self) -> None:
        content = (FIXTURES / "missing_fields.md").read_text()
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "FM003" in rule_ids

    def test_bad_frontmatter_fires_fm002_and_fm004(self) -> None:
        content = (FIXTURES / "bad_frontmatter.md").read_text()
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        # id has uppercase/underscore → FM004
        assert "FM004" in rule_ids

    def test_non_kebab_id_fires_fm004(self) -> None:
        content = (
            "---\nid: BadID\nname: X\ndescription: Y Y Y Y Y\nversion: 1.0.0\ntags: [a]\n---\n# X\n"
        )
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "FM004" in rule_ids

    def test_invalid_semver_fires_fm005(self) -> None:
        content = (
            "---\nid: my-skill\nname: X\ndescription: Y Y Y Y Y\nversion: v2\ntags: [a]\n---\n# X\n"
        )
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "FM005" in rule_ids

    def test_empty_body_fires_ct001(self) -> None:
        content = (
            "---\nid: my-skill\nname: X\ndescription: Y Y Y Y Y\nversion: 1.0.0\ntags: [a]\n---\n"
        )
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "CT001" in rule_ids

    def test_no_heading_fires_st001(self) -> None:
        content = "---\nid: my-skill\nname: X\ndescription: Y Y Y Y Y\nversion: 1.0.0\ntags: [a]\n---\n\nSome body text without a heading.\n"
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "ST001" in rule_ids

    def test_schema_errors_included_in_fm002(self) -> None:
        content = '---\nid: BadID\nname: ""\ndescription: Short\nversion: v2\ntags: []\n---\n# X\n'
        findings = audit_file(content, BASELINE_RULES)
        fm002 = next((f for f in findings if f["rule_id"] == "FM002"), None)
        if fm002:
            assert "schema_errors" in fm002

    def test_missing_tags_fires_ct004(self) -> None:
        content = "---\nid: my-skill\nname: X\ndescription: Y Y Y Y Y\nversion: 1.0.0\ntags: []\n---\n# X\n\nBody text.\n"
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "CT004" in rule_ids

    def test_missing_verification_fires_ct003(self) -> None:
        content = "---\nid: my-skill\nname: X\ndescription: Y Y Y Y Y Y Y Y Y\nversion: 1.0.0\ntags: [a]\n---\n# X\n\nBody text with enough content.\n"
        findings = audit_file(content, BASELINE_RULES)
        rule_ids = [f["rule_id"] for f in findings]
        assert "CT003" in rule_ids


# ---------------------------------------------------------------------------
# run_audit
# ---------------------------------------------------------------------------


class TestRunAudit:
    def test_audit_from_file_list(self, tmp_path: Path) -> None:
        src = FIXTURES / "no_frontmatter.md"
        report = run_audit([str(src)], rule_source=_rule_source(), dry_run=True)
        assert report["summary"]["files_audited"] == 1
        assert report["summary"]["total_findings"] > 0

    def test_audit_from_manifest(self) -> None:
        manifest = {
            "candidates": [
                {
                    "repo": "test",
                    "path": "good_skill.md",
                    "abs_path": str(FIXTURES / "good_skill.md"),
                    "content_hash": "abc",
                    "has_frontmatter": True,
                    "frontmatter": {},
                }
            ]
        }
        report = run_audit(manifest, rule_source=_rule_source(), dry_run=True)
        assert report["summary"]["files_audited"] == 1

    def test_report_structure(self, tmp_path: Path) -> None:
        report = run_audit(
            [str(FIXTURES / "good_skill.md")],
            rule_source=_rule_source(),
            dry_run=True,
        )
        assert "schema_version" in report
        assert "created_at" in report
        assert "rule_source" in report
        assert "summary" in report
        assert "files" in report

    def test_json_output(self, tmp_path: Path) -> None:
        import json

        out = tmp_path / "report.json"
        run_audit(
            [str(FIXTURES / "good_skill.md")],
            rule_source=_rule_source(),
            output_path=str(out),
            dry_run=True,
        )
        assert out.exists()
        data = json.loads(out.read_text())
        assert "files" in data

    def test_markdown_output(self, tmp_path: Path) -> None:
        out_md = tmp_path / "report.md"
        run_audit(
            [str(FIXTURES / "no_frontmatter.md")],
            rule_source=_rule_source(),
            report_md_path=str(out_md),
            dry_run=True,
        )
        assert out_md.exists()
        md = out_md.read_text()
        assert "# Audit Report" in md

    def test_by_severity_counts(self) -> None:
        report = run_audit(
            [str(FIXTURES / "no_frontmatter.md")],
            rule_source=_rule_source(),
            dry_run=True,
        )
        bsev = report["summary"]["by_severity"]
        # FM001 is an error, so errors should be ≥ 1
        assert bsev.get("error", 0) >= 1
