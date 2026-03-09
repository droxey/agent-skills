"""
Fix subcommand – apply safe, deterministic fixes in-place.

All fixes default to dry-run; ``--apply`` is required for mutations.
After applying fixes, a re-audit is run automatically to show improvement.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

from .audit import run_audit
from .rules import RuleSource
from .schema import extract_frontmatter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fixers – one per fixable rule id
# ---------------------------------------------------------------------------


def _fix_fm001(content: str, fm: dict | None, body: str) -> str | None:
    """Add minimal YAML frontmatter stub."""
    if fm is not None:
        return None  # already has frontmatter

    # Try to derive a name from the first heading
    heading_match = re.search(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)
    name = heading_match.group(1).strip() if heading_match else "Untitled Skill"
    safe_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled-skill"

    stub = (
        "---\n"
        f'id: "{safe_id}"\n'
        f'name: "{name}"\n'
        'description: "TODO: describe this skill."\n'
        'version: "0.1.0"\n'
        "tags: []\n"
        "---\n"
    )
    return stub + content


def _fix_fm004(content: str, fm: dict | None, body: str) -> str | None:
    """Normalise skill id to kebab-case."""
    if fm is None or "id" not in fm:
        return None
    old_id = str(fm["id"])
    new_id = re.sub(r"[^a-z0-9]+", "-", old_id.lower()).strip("-")
    if old_id == new_id:
        return None
    return content.replace(f"id: {old_id}", f"id: {new_id}", 1).replace(
        f'id: "{old_id}"', f'id: "{new_id}"', 1
    )


def _fix_fm005(content: str, fm: dict | None, body: str) -> str | None:
    """Set version to '0.1.0' if it is not valid semver."""
    if fm is None or "version" not in fm:
        return None
    ver = str(fm["version"])
    if re.match(r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$", ver):
        return None
    return re.sub(
        r"(^version:\s*)(.+)$",
        r'\g<1>"0.1.0"',
        content,
        count=1,
        flags=re.MULTILINE,
    )


def _fix_st001(content: str, fm: dict | None, body: str) -> str | None:
    """Prepend a heading derived from the skill name."""
    if re.search(r"^#{1,6}\s+\S", body, re.MULTILINE):
        return None
    name = (fm or {}).get("name", "Skill")
    # Find the end of the frontmatter block
    fm_end = re.search(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_end:
        insert_pos = fm_end.end()
        return content[:insert_pos] + f"# {name}\n\n" + content[insert_pos:]
    return f"# {name}\n\n" + content


_FIXERS: dict[str, Any] = {
    "FM001": _fix_fm001,
    "FM004": _fix_fm004,
    "FM005": _fix_fm005,
    "ST001": _fix_st001,
}


# ---------------------------------------------------------------------------
# Fix runner
# ---------------------------------------------------------------------------


def run_fix(
    plan: dict[str, Any],
    *,
    apply: bool = False,
    rule_source: RuleSource | None = None,
    offline: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Apply auto-fixes from *plan* to skill files.

    Parameters
    ----------
    plan:
        Output of :func:`skillsctl.plan.run_plan`.
    apply:
        If False (default), no files are written.
    rule_source:
        Rule source for the post-fix re-audit.
    dry_run:
        Alias for ``not apply``; if True, nothing is written.

    Returns
    -------
    dict
        Fix report with before/after finding counts and a re-audit summary.
    """
    effective_apply = apply and not dry_run

    actions: list[dict[str, Any]] = []
    touched: dict[str, str] = {}  # abs_path -> modified content

    # Group fixable items by file
    fixable_items = [it for it in plan.get("items", []) if it.get("fixable")]

    for item in fixable_items:
        abs_path = item.get("abs_path", "")
        rule_id = item.get("rule_id", "")
        fixer = _FIXERS.get(rule_id)
        if fixer is None or not abs_path:
            continue

        # Work on the (possibly already modified) content
        if abs_path in touched:
            content = touched[abs_path]
        else:
            try:
                content = Path(abs_path).read_text(errors="replace")
            except OSError as exc:
                logger.warning("Cannot read %s: %s", abs_path, exc)
                continue

        fm, body = extract_frontmatter(content)
        new_content = fixer(content, fm, body)
        if new_content is None or new_content == content:
            continue  # nothing to fix

        touched[abs_path] = new_content
        actions.append(
            {
                "abs_path": abs_path,
                "path": item.get("path", ""),
                "repo": item.get("repo", ""),
                "rule_id": rule_id,
                "applied": effective_apply,
                "diff_summary": f"Rule {rule_id} fix applied.",
            }
        )

    # Write files if apply mode
    if effective_apply:
        for abs_path, new_content in touched.items():
            try:
                Path(abs_path).write_text(new_content)
                logger.info("Fixed %s", abs_path)
            except OSError as exc:
                logger.error("Could not write %s: %s", abs_path, exc)
    else:
        logger.info(
            "Dry-run: %d fix actions would be applied (pass --apply to write).",
            len(actions),
        )

    # Re-audit the touched files (or originals in dry-run)
    files_to_reaudit = list(touched.keys()) if touched else []
    post_audit: dict[str, Any] = {}
    if files_to_reaudit:
        # In dry-run, synthesise temporary content for re-audit
        if not effective_apply:
            import os
            import tempfile

            tmp_paths: list[str] = []
            tmp_dir = tempfile.mkdtemp(prefix="skillsctl_fix_")
            try:
                for ap, new_c in touched.items():
                    fname = os.path.basename(ap)
                    tp = os.path.join(tmp_dir, fname)
                    Path(tp).write_text(new_c)
                    tmp_paths.append(tp)
                post_audit = run_audit(
                    tmp_paths,
                    rule_source=rule_source,
                    offline=offline,
                    dry_run=True,
                )
            finally:
                import shutil

                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            post_audit = run_audit(
                files_to_reaudit,
                rule_source=rule_source,
                offline=offline,
                dry_run=False,
            )

    report: dict[str, Any] = {
        "schema_version": "1",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "dry_run": not effective_apply,
        "applied": effective_apply,
        "actions": actions,
        "actions_count": len(actions),
        "post_fix_audit_summary": post_audit.get("summary", {}),
    }
    return report
