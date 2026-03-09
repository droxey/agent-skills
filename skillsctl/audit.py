"""
Audit subcommand – evaluate candidate skill files against the rule set.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Any

from .rules import RuleSource, fetch_rules
from .schema import extract_frontmatter, validate_frontmatter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-rule checkers
# ---------------------------------------------------------------------------


def _check_fm001(content: str, fm: dict | None, body: str) -> bool:
    """FM001 – missing frontmatter."""
    return fm is None


def _check_fm002(content: str, fm: dict | None, body: str) -> bool:
    """FM002 – invalid frontmatter schema."""
    if fm is None:
        return False  # FM001 already covers this
    return bool(validate_frontmatter(fm))


def _check_fm003(content: str, fm: dict | None, body: str) -> bool:
    """FM003 – missing required field."""
    if fm is None:
        return False
    required = {"id", "name", "description", "version", "tags"}
    missing = required - set(fm.keys())
    return bool(missing)


def _check_fm004(content: str, fm: dict | None, body: str) -> bool:
    """FM004 – non-kebab-case id."""
    if fm is None or "id" not in fm:
        return False
    return not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", str(fm["id"]))


def _check_fm005(content: str, fm: dict | None, body: str) -> bool:
    """FM005 – invalid semver."""
    if fm is None or "version" not in fm:
        return False
    return not re.match(r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$", str(fm["version"]))


def _check_ct001(content: str, fm: dict | None, body: str) -> bool:
    """CT001 – no descriptive text in body."""
    stripped = body.strip()
    return len(stripped) < 20


def _check_ct002(content: str, fm: dict | None, body: str) -> bool:
    """CT002 – no usage example."""
    markers = ["example", "usage", "sample", "e.g.", "```"]
    lower = body.lower()
    return not any(m in lower for m in markers)


def _check_ct003(content: str, fm: dict | None, body: str) -> bool:
    """CT003 – missing verification field."""
    if fm is None:
        return False
    return "verification" not in fm or not fm["verification"]


def _check_ct004(content: str, fm: dict | None, body: str) -> bool:
    """CT004 – missing or empty tags."""
    if fm is None:
        return False
    tags = fm.get("tags", [])
    return not isinstance(tags, list) or len(tags) == 0


def _check_st001(content: str, fm: dict | None, body: str) -> bool:
    """ST001 – no Markdown heading."""
    return not re.search(r"^#{1,6}\s+\S", body, re.MULTILINE)


_CHECKERS: dict[str, Any] = {
    "FM001": _check_fm001,
    "FM002": _check_fm002,
    "FM003": _check_fm003,
    "FM004": _check_fm004,
    "FM005": _check_fm005,
    "CT001": _check_ct001,
    "CT002": _check_ct002,
    "CT003": _check_ct003,
    "CT004": _check_ct004,
    "ST001": _check_st001,
}


# ---------------------------------------------------------------------------
# Audit core
# ---------------------------------------------------------------------------


def audit_file(
    content: str,
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Run all applicable rule checkers against *content*.

    Returns a list of finding dicts for rules that fired.
    """
    fm, body = extract_frontmatter(content)
    findings: list[dict[str, Any]] = []

    for rule in rules:
        rule_id = rule.get("id", "")
        checker = _CHECKERS.get(rule_id)
        if checker is None:
            continue
        try:
            fired = checker(content, fm, body)
        except Exception as exc:
            logger.debug("Checker %s raised: %s", rule_id, exc)
            fired = False
        if fired:
            finding: dict[str, Any] = {
                "rule_id": rule_id,
                "name": rule.get("name", rule_id),
                "severity": rule.get("severity", "info"),
                "description": rule.get("description", ""),
                "effort": rule.get("effort", "unknown"),
                "fixable": rule.get("fixable", False),
            }
            # Add extra detail for schema violations
            if rule_id == "FM002" and fm is not None:
                finding["schema_errors"] = validate_frontmatter(fm)
            if rule_id == "FM003" and fm is not None:
                required = {"id", "name", "description", "version", "tags"}
                finding["missing_fields"] = sorted(required - set(fm.keys()))
            findings.append(finding)

    return findings


def run_audit(
    manifest_or_files: dict[str, Any] | list[str],
    *,
    rule_source: RuleSource | None = None,
    output_path: str | None = None,
    report_md_path: str | None = None,
    offline: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Audit candidate files from a scan manifest or a list of file paths.

    Returns a structured audit report dict.
    """
    if rule_source is None:
        rule_source = fetch_rules(offline=offline)

    rules = rule_source.rules

    # Normalise input
    candidates: list[dict[str, Any]] = []
    if isinstance(manifest_or_files, dict):
        candidates = manifest_or_files.get("candidates", [])
    else:
        for fp in manifest_or_files:
            p = Path(fp)
            try:
                content = p.read_text(errors="replace")
            except OSError as exc:
                logger.warning("Cannot read %s: %s", fp, exc)
                continue
            from .schema import content_hash

            fm, _ = extract_frontmatter(content)
            candidates.append(
                {
                    "repo": str(p.parent),
                    "path": p.name,
                    "abs_path": str(p),
                    "content_hash": content_hash(content),
                    "has_frontmatter": fm is not None,
                    "frontmatter": fm or {},
                }
            )

    file_results: list[dict[str, Any]] = []
    total_findings = 0

    for cand in candidates:
        abs_path = cand.get("abs_path", "")
        content = ""
        if abs_path:
            try:
                content = Path(abs_path).read_text(errors="replace")
            except OSError:
                pass

        findings = audit_file(content, rules)
        total_findings += len(findings)

        file_results.append(
            {
                "repo": cand.get("repo", ""),
                "path": cand.get("path", ""),
                "abs_path": abs_path,
                "content_hash": cand.get("content_hash", ""),
                "finding_count": len(findings),
                "findings": findings,
            }
        )

    report: dict[str, Any] = {
        "schema_version": "1",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "dry_run": dry_run,
        "rule_source": rule_source.as_dict(),
        "summary": {
            "files_audited": len(file_results),
            "total_findings": total_findings,
            "by_severity": _count_by_severity(file_results),
        },
        "files": file_results,
    }

    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2))
        logger.info("Audit JSON report written to %s", output_path)

    if report_md_path:
        Path(report_md_path).write_text(_render_markdown(report))
        logger.info("Audit Markdown report written to %s", report_md_path)

    return report


def _count_by_severity(file_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    for fr in file_results:
        for finding in fr.get("findings", []):
            sev = finding.get("severity", "info")
            counts[sev] = counts.get(sev, 0) + 1
    return counts


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Audit Report",
        "",
        f"**Generated:** {report['created_at']}  ",
        f"**Dry-run:** {report['dry_run']}  ",
        "",
        "## Rule Source",
        "",
    ]
    rs = report.get("rule_source", {})
    lines += [
        f"- **URL:** {rs.get('source_url', 'N/A')}",
        f"- **Commit SHA:** `{rs.get('commit_sha', 'N/A')}`",
        f"- **Fetched at:** {rs.get('fetched_at', 'N/A')}",
        f"- **Using baseline:** {rs.get('is_baseline', True)}",
        "",
        "## Summary",
        "",
    ]
    s = report.get("summary", {})
    by_sev = s.get("by_severity", {})
    lines += [
        "| Files audited | Total findings | Errors | Warnings | Info |",
        "|---|---|---|---|---|",
        f"| {s.get('files_audited', 0)} | {s.get('total_findings', 0)} "
        f"| {by_sev.get('error', 0)} | {by_sev.get('warning', 0)} | {by_sev.get('info', 0)} |",
        "",
        "## Findings",
        "",
    ]
    for fr in report.get("files", []):
        if not fr.get("findings"):
            continue
        lines.append(f"### `{fr.get('repo', '')}/{fr.get('path', '')}`")
        lines.append("")
        lines.append("| Rule | Severity | Description |")
        lines.append("|---|---|---|")
        for f in fr["findings"]:
            lines.append(f"| `{f['rule_id']}` | {f['severity']} | {f['description']} |")
        lines.append("")
    return "\n".join(lines)
