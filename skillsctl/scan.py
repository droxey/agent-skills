"""
Scan subcommand – discover candidate skill/prompt files in target repos.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .schema import content_hash, extract_frontmatter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Heuristics: patterns that suggest a file is a skill/prompt
# ---------------------------------------------------------------------------

# File name patterns
_NAME_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"prompt", re.I),
    re.compile(r"skill", re.I),
    re.compile(r"instruction", re.I),
    re.compile(r"system[-_]?message", re.I),
    re.compile(r"template", re.I),
    re.compile(r"\.prompt\.", re.I),
]

# Directory name patterns
_DIR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"prompts?$", re.I),
    re.compile(r"skills?$", re.I),
    re.compile(r"instructions?$", re.I),
    re.compile(r"templates?$", re.I),
    re.compile(r"agents?$", re.I),
    re.compile(r"ai$", re.I),
    re.compile(r"copilot$", re.I),
    re.compile(r"llm$", re.I),
]

# Content-based signals
_CONTENT_SIGNALS = [
    re.compile(r"^---\s*\n", re.MULTILINE),  # YAML frontmatter
    re.compile(r"\byou are\b", re.I),
    re.compile(r"\bsystem prompt\b", re.I),
    re.compile(r"\binstruction\b", re.I),
    re.compile(r"\bact as\b", re.I),
    re.compile(r"\b{{.*?}}\b"),  # template vars
    re.compile(r"\{[A-Z_]+\}"),  # placeholder vars
]

_EXTENSIONS = {".md", ".markdown", ".txt", ".prompt", ".skill"}
_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def _is_candidate(path: Path, content: str | None = None) -> bool:
    """Return True if *path* looks like a skill/prompt file."""
    # Extension filter
    if path.suffix.lower() not in _EXTENSIONS:
        return False

    # Name-based signals
    for pat in _NAME_PATTERNS:
        if pat.search(path.name):
            return True

    # Directory-based signals
    for part in path.parts:
        for pat in _DIR_PATTERNS:
            if pat.search(part):
                return True

    # Content-based signals (expensive – only if content provided)
    if content is not None:
        hits = sum(1 for s in _CONTENT_SIGNALS if s.search(content))
        if hits >= 2:
            return True

    return False


def _scan_directory(root: Path, repo_label: str) -> list[dict[str, Any]]:
    """Walk *root* and return a list of candidate file entries."""
    candidates: list[dict[str, Any]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel = fpath.relative_to(root)

            # Quick check on extension + name before reading content
            if fpath.suffix.lower() not in _EXTENSIONS:
                continue

            try:
                content = fpath.read_text(errors="replace")
            except OSError:
                continue

            if not _is_candidate(fpath, content):
                continue

            fm, body = extract_frontmatter(content)
            entry: dict[str, Any] = {
                "repo": repo_label,
                "path": str(rel),
                "abs_path": str(fpath),
                "content_hash": content_hash(content),
                "has_frontmatter": fm is not None,
                "frontmatter": fm or {},
                "size_bytes": fpath.stat().st_size,
            }
            candidates.append(entry)

    return candidates


def _resolve_repo_url(repo_spec: str) -> str:
    """Convert 'owner/repo' shorthand to a full GitHub HTTPS URL."""
    if repo_spec.startswith(("http://", "https://", "git@")):
        return repo_spec
    if "/" in repo_spec and not repo_spec.startswith("/"):
        return f"https://github.com/{repo_spec}.git"
    return repo_spec


def _clone_repo(url: str, target_dir: str) -> str | None:
    """Shallow-clone *url* into *target_dir*, return HEAD SHA or None on error."""
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", "--quiet", url, target_dir],
            capture_output=True,
            timeout=120,
            check=True,
        )
        result = subprocess.run(
            ["git", "-C", target_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "Clone failed for %s: %s",
            url,
            exc.stderr.decode(errors="replace") if exc.stderr else str(exc),
        )
        return None


def run_scan(
    repos: list[str],
    *,
    local_paths: list[str] | None = None,
    output_path: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Scan repositories (remote or local) for candidate skill files.

    Parameters
    ----------
    repos:
        List of ``owner/repo`` slugs or full Git URLs to clone & scan.
    local_paths:
        List of already-checked-out directory paths to scan directly.
    output_path:
        If provided, write the manifest JSON to this file.
    dry_run:
        Included for API consistency; scan is always read-only.

    Returns
    -------
    dict
        Scan manifest with metadata and candidate list.
    """
    manifest: dict[str, Any] = {
        "schema_version": "1",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "dry_run": dry_run,
        "sources": [],
        "candidates": [],
    }

    # Scan local paths
    for lp in local_paths or []:
        root = Path(lp).resolve()
        if not root.is_dir():
            logger.warning("Local path not found: %s", lp)
            continue
        label = root.name
        entries = _scan_directory(root, label)
        manifest["sources"].append({"type": "local", "path": str(root), "label": label})
        manifest["candidates"].extend(entries)
        logger.info("Scanned %s (%d candidates)", root, len(entries))

    # Clone and scan remote repos
    with tempfile.TemporaryDirectory(prefix="skillsctl_scan_") as tmpdir:
        for repo_spec in repos:
            url = _resolve_repo_url(repo_spec)
            label = repo_spec.rstrip("/").split("/")[-1].replace(".git", "")
            # use owner/repo as label if available
            if "/" in repo_spec and not repo_spec.startswith(("http://", "https://", "git@")):
                label = repo_spec.strip()

            clone_dir = str(Path(tmpdir) / label.replace("/", "_"))
            sha = _clone_repo(url, clone_dir)
            if sha is None:
                manifest["sources"].append(
                    {"type": "remote", "url": url, "label": label, "error": "clone_failed"}
                )
                continue

            entries = _scan_directory(Path(clone_dir), label)
            manifest["sources"].append(
                {"type": "remote", "url": url, "label": label, "commit_sha": sha}
            )
            manifest["candidates"].extend(entries)
            logger.info("Scanned %s @ %s (%d candidates)", label, sha[:12], len(entries))

    if output_path:
        Path(output_path).write_text(json.dumps(manifest, indent=2))
        logger.info("Manifest written to %s", output_path)

    return manifest
