"""
Migrate subcommand – move skill files into this repo under skills/<domain>/...
with stable IDs and optional source-repo pointer files.

Safety rails:
- Requires ``--apply`` for any writes.
- Requires ``--allow-delete`` to delete source files.
"""

from __future__ import annotations

import datetime
import logging
import re
from pathlib import Path
from typing import Any

import yaml

from .schema import build_stable_id, extract_frontmatter

logger = logging.getLogger(__name__)

_SKILLS_ROOT = Path(__file__).parent.parent / "skills"


def _domain_from_tags(tags: list[str] | None) -> str:
    """Pick the first tag as the domain directory, defaulting to 'general'."""
    if tags and isinstance(tags, list) and tags:
        tag = str(tags[0]).lower()
        return re.sub(r"[^a-z0-9-]", "-", tag).strip("-") or "general"
    return "general"


def _ensure_stable_id(fm: dict[str, Any], repo: str, rel_path: str) -> dict[str, Any]:
    """Return a copy of *fm* with a stable, deterministic id."""
    fm = dict(fm)
    if not fm.get("id"):
        fm["id"] = build_stable_id(repo, rel_path)
    return fm


def _write_frontmatter(fm: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.dump(fm, sort_keys=False, allow_unicode=True) + "---\n" + body


def _pointer_content(skill_id: str, dest_rel: str, skills_repo: str) -> str:
    return (
        f"<!-- This file was migrated to [{skills_repo}]"
        f"(https://github.com/{skills_repo}/blob/main/{dest_rel}). -->\n\n"
        f"**Skill `{skill_id}` has been migrated.**  \n"
        f"See: https://github.com/{skills_repo}/blob/main/{dest_rel}\n"
    )


def run_migrate(
    manifest: dict[str, Any],
    *,
    skills_root: str | Path | None = None,
    skills_repo: str = "droxey/agent-skills",
    apply: bool = False,
    allow_delete: bool = False,
    dry_run: bool = True,
    write_pointer: bool = True,
) -> dict[str, Any]:
    """
    Migrate candidate skills from a scan manifest into *skills_root*.

    Parameters
    ----------
    manifest:
        Output of :func:`skillsctl.scan.run_scan`.
    skills_root:
        Directory under which skills are organised (default: ``skills/``).
    skills_repo:
        GitHub slug of the target repository (used for pointer links).
    apply:
        If False, no files are written or deleted.
    allow_delete:
        If True (and ``apply`` is True), delete source files after copying.
    dry_run:
        Alias for ``not apply``; takes precedence.
    write_pointer:
        If True and ``apply`` is True, write a pointer stub in the source repo.
    """
    effective_apply = apply and not dry_run
    effective_delete = effective_apply and allow_delete

    root = Path(skills_root) if skills_root else _SKILLS_ROOT
    actions: list[dict[str, Any]] = []

    for cand in manifest.get("candidates", []):
        abs_path_str = cand.get("abs_path", "")
        rel_path = cand.get("path", "")
        repo = cand.get("repo", "unknown")

        if not abs_path_str:
            continue
        src = Path(abs_path_str)
        if not src.exists():
            continue

        try:
            content = src.read_text(errors="replace")
        except OSError as exc:
            logger.warning("Cannot read %s: %s", src, exc)
            continue

        fm, body = extract_frontmatter(content)
        if fm is None:
            fm = {}

        fm = _ensure_stable_id(fm, repo, rel_path)
        skill_id = fm["id"]
        domain = _domain_from_tags(fm.get("tags"))

        # Destination path
        dest_rel = f"skills/{domain}/{skill_id}.md"
        dest = root.parent / dest_rel  # root is skills/, so go one up

        # Stamp migration metadata
        fm["source"] = f"https://github.com/{repo}"
        fm["migrated_at"] = (
            datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        )

        new_content = _write_frontmatter(fm, body)
        action: dict[str, Any] = {
            "skill_id": skill_id,
            "repo": repo,
            "source_path": abs_path_str,
            "dest_path": str(dest),
            "dest_rel": dest_rel,
            "domain": domain,
            "applied": False,
            "deleted_source": False,
            "wrote_pointer": False,
        }

        if effective_apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(new_content)
            action["applied"] = True
            logger.info("Migrated %s -> %s", src, dest)

            if write_pointer:
                pointer = _pointer_content(skill_id, dest_rel, skills_repo)
                try:
                    src.write_text(pointer)
                    action["wrote_pointer"] = True
                    logger.info("Wrote pointer in %s", src)
                except OSError as exc:
                    logger.warning("Could not write pointer in %s: %s", src, exc)

            if effective_delete and not write_pointer:
                try:
                    src.unlink()
                    action["deleted_source"] = True
                    logger.info("Deleted source %s", src)
                except OSError as exc:
                    logger.warning("Could not delete %s: %s", src, exc)
        else:
            logger.info(
                "Dry-run: would migrate %s -> %s (pass --apply to write).",
                src,
                dest,
            )

        actions.append(action)

    report: dict[str, Any] = {
        "schema_version": "1",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "dry_run": not effective_apply,
        "applied": effective_apply,
        "allow_delete": allow_delete,
        "skills_root": str(root),
        "skills_repo": skills_repo,
        "actions": actions,
        "summary": {
            "total": len(actions),
            "applied": sum(1 for a in actions if a["applied"]),
            "pointers_written": sum(1 for a in actions if a["wrote_pointer"]),
            "deleted": sum(1 for a in actions if a["deleted_source"]),
        },
    }
    return report
