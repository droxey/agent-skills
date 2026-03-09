"""
Plan subcommand – produce a prioritised improvement plan from audit findings.
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from .rules import SEVERITY_ORDER

logger = logging.getLogger(__name__)

# Effort → numeric cost (lower = easier to fix)
_EFFORT_COST = {"low": 1, "medium": 2, "high": 3, "unknown": 2}

# Risk: fixable + low-effort = low risk; else medium/high
_RISK_MATRIX = {
    (True, "low"): "low",
    (True, "medium"): "medium",
    (True, "high"): "high",
    (False, "low"): "medium",
    (False, "medium"): "high",
    (False, "high"): "high",
}


def _priority_score(finding: dict[str, Any]) -> float:
    """
    Compute a priority score for a finding.

    Lower score = higher priority.  Ordering:
      1. severity (error < warning < info)
      2. effort (low < medium < high)
      3. fixable (fixable first)
    """
    sev = SEVERITY_ORDER.get(finding.get("severity", "info"), 2)
    effort = _EFFORT_COST.get(finding.get("effort", "unknown"), 2)
    fixable = 0 if finding.get("fixable") else 1
    return sev * 10 + effort + fixable * 0.5


def run_plan(
    audit_report: dict[str, Any],
    *,
    output_path: str | None = None,
    report_md_path: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Build a prioritised improvement plan from an audit report.

    Each item in the plan represents an actionable finding with:
    - priority rank
    - file target
    - suggested action
    - risk assessment
    """
    items: list[dict[str, Any]] = []

    for file_result in audit_report.get("files", []):
        repo = file_result.get("repo", "")
        path = file_result.get("path", "")
        abs_path = file_result.get("abs_path", "")

        for finding in file_result.get("findings", []):
            risk = _RISK_MATRIX.get(
                (bool(finding.get("fixable")), finding.get("effort", "unknown")),
                "medium",
            )
            item: dict[str, Any] = {
                "repo": repo,
                "path": path,
                "abs_path": abs_path,
                "rule_id": finding["rule_id"],
                "name": finding.get("name", finding["rule_id"]),
                "severity": finding.get("severity", "info"),
                "effort": finding.get("effort", "unknown"),
                "fixable": finding.get("fixable", False),
                "risk": risk,
                "description": finding.get("description", ""),
                "action": _suggested_action(finding),
                "_score": _priority_score(finding),
            }
            items.append(item)

    # Sort by score ascending (highest priority first)
    items.sort(key=lambda x: x["_score"])

    # Assign rank
    for i, item in enumerate(items, start=1):
        item["rank"] = i
        del item["_score"]

    plan: dict[str, Any] = {
        "schema_version": "1",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "dry_run": dry_run,
        "rule_source": audit_report.get("rule_source", {}),
        "summary": {
            "total_items": len(items),
            "fixable_items": sum(1 for it in items if it.get("fixable")),
            "by_severity": _count_by_field(items, "severity"),
            "by_risk": _count_by_field(items, "risk"),
        },
        "items": items,
    }

    if output_path:
        Path(output_path).write_text(json.dumps(plan, indent=2))
        logger.info("Plan JSON written to %s", output_path)

    if report_md_path:
        Path(report_md_path).write_text(_render_markdown(plan))
        logger.info("Plan Markdown written to %s", report_md_path)

    return plan


def _suggested_action(finding: dict[str, Any]) -> str:
    actions = {
        "FM001": "Add YAML frontmatter block with required fields.",
        "FM002": "Fix frontmatter to match the skill schema.",
        "FM003": "Add missing required frontmatter fields.",
        "FM004": "Rename `id` to lower-kebab-case (e.g. `my-skill`).",
        "FM005": "Update `version` to semver format (e.g. `1.0.0`).",
        "CT001": "Add descriptive body text explaining the skill.",
        "CT002": "Add a usage example or sample prompt.",
        "CT003": "Add a `verification` field to frontmatter.",
        "CT004": "Add at least one tag to the `tags` array.",
        "ST001": "Add a Markdown heading (e.g. `# Skill Name`) to the body.",
    }
    return actions.get(finding.get("rule_id", ""), "Review and address the finding.")


def _count_by_field(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(field, "unknown")
        counts[val] = counts.get(val, 0) + 1
    return counts


def _render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Improvement Plan",
        "",
        f"**Generated:** {plan['created_at']}  ",
        f"**Dry-run:** {plan['dry_run']}  ",
        "",
        "## Summary",
        "",
    ]
    s = plan.get("summary", {})
    lines += [
        f"- **Total items:** {s.get('total_items', 0)}",
        f"- **Auto-fixable:** {s.get('fixable_items', 0)}",
        "",
        "### By Severity",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for sev, cnt in sorted(
        s.get("by_severity", {}).items(),
        key=lambda kv: SEVERITY_ORDER.get(kv[0], 99),
    ):
        lines.append(f"| {sev} | {cnt} |")

    lines += [
        "",
        "### By Risk",
        "",
        "| Risk | Count |",
        "|---|---|",
    ]
    for risk, cnt in sorted(s.get("by_risk", {}).items()):
        lines.append(f"| {risk} | {cnt} |")

    lines += [
        "",
        "## Prioritised Action Items",
        "",
        "| # | File | Rule | Severity | Effort | Risk | Fixable | Action |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for item in plan.get("items", []):
        fix_mark = "✅" if item.get("fixable") else "❌"
        lines.append(
            f"| {item['rank']} "
            f"| `{item.get('repo', '')}/{item.get('path', '')}` "
            f"| `{item['rule_id']}` "
            f"| {item['severity']} "
            f"| {item['effort']} "
            f"| {item['risk']} "
            f"| {fix_mark} "
            f"| {item['action']} |"
        )

    lines.append("")
    return "\n".join(lines)
