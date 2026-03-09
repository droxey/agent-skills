"""
Rule fetching and management.

Fetches best-practice rules from ``mgechev/skills-best-practices`` at runtime
via the GitHub archive API.  If that fails the tool continues with a built-in
baseline rule set and emits a clear warning.
"""

from __future__ import annotations

import datetime
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

BEST_PRACTICES_REPO = "mgechev/skills-best-practices"
BEST_PRACTICES_URL = f"https://github.com/{BEST_PRACTICES_REPO}"

# ---------------------------------------------------------------------------
# Built-in baseline rules
# ---------------------------------------------------------------------------

BASELINE_RULES: list[dict[str, Any]] = [
    {
        "id": "FM001",
        "name": "missing-frontmatter",
        "severity": "error",
        "description": "Skill file has no YAML frontmatter block.",
        "effort": "low",
        "fixable": True,
    },
    {
        "id": "FM002",
        "name": "invalid-frontmatter-schema",
        "severity": "error",
        "description": "YAML frontmatter does not match the skill schema.",
        "effort": "low",
        "fixable": False,
    },
    {
        "id": "FM003",
        "name": "missing-required-field",
        "severity": "error",
        "description": "A required frontmatter field is absent or empty.",
        "effort": "low",
        "fixable": False,
    },
    {
        "id": "FM004",
        "name": "non-kebab-id",
        "severity": "warning",
        "description": "Skill `id` is not in lower-kebab-case format.",
        "effort": "low",
        "fixable": True,
    },
    {
        "id": "FM005",
        "name": "invalid-semver",
        "severity": "warning",
        "description": "Skill `version` does not follow semver (MAJOR.MINOR.PATCH).",
        "effort": "low",
        "fixable": True,
    },
    {
        "id": "CT001",
        "name": "no-description",
        "severity": "warning",
        "description": "Skill body contains no descriptive text below the frontmatter.",
        "effort": "medium",
        "fixable": False,
    },
    {
        "id": "CT002",
        "name": "no-usage-example",
        "severity": "info",
        "description": "Skill body contains no usage example or sample prompt.",
        "effort": "medium",
        "fixable": False,
    },
    {
        "id": "CT003",
        "name": "missing-verification",
        "severity": "info",
        "description": "Frontmatter lacks a `verification` guidance field.",
        "effort": "low",
        "fixable": False,
    },
    {
        "id": "CT004",
        "name": "missing-tags",
        "severity": "warning",
        "description": "Skill has no taxonomy tags.",
        "effort": "low",
        "fixable": False,
    },
    {
        "id": "ST001",
        "name": "heading-missing",
        "severity": "info",
        "description": "Skill body has no Markdown heading.",
        "effort": "low",
        "fixable": True,
    },
]

# Severity ordering for plan prioritisation
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class RuleSource:
    """Container for rules fetched from an external or built-in source."""

    def __init__(
        self,
        rules: list[dict[str, Any]],
        *,
        source_url: str = "(built-in)",
        commit_sha: str = "N/A",
        fetched_at: str = "",
        is_baseline: bool = True,
    ) -> None:
        self.rules = rules
        self.source_url = source_url
        self.commit_sha = commit_sha
        self.fetched_at = fetched_at or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat().replace("+00:00", "Z")
        self.is_baseline = is_baseline

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "commit_sha": self.commit_sha,
            "fetched_at": self.fetched_at,
            "is_baseline": self.is_baseline,
            "rule_count": len(self.rules),
        }


def _get_remote_sha(repo: str) -> str | None:
    """Return the HEAD commit SHA of the default branch using git ls-remote."""
    url = f"https://github.com/{repo}.git"
    try:
        result = subprocess.run(
            ["git", "ls-remote", url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            line = result.stdout.strip().split("\n")[0]
            if line:
                return line.split()[0]
    except Exception:
        pass
    return None


def _clone_and_parse(repo: str, sha: str) -> list[dict[str, Any]] | None:
    """
    Shallow-clone *repo* into a temp dir, look for a rules definition file
    (JSON or YAML), and return the rules list.  Returns None on failure.
    """
    url = f"https://github.com/{repo}.git"
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(
                ["git", "clone", "--depth=1", "--quiet", url, tmp],
                capture_output=True,
                timeout=60,
                check=True,
            )
        except Exception as exc:
            logger.debug("Clone failed: %s", exc)
            return None

        tmp_path = Path(tmp)
        candidates = [
            tmp_path / "rules.json",
            tmp_path / "rules.yaml",
            tmp_path / "rules.yml",
            tmp_path / "skills-best-practices.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    import yaml

                    raw = candidate.read_text()
                    data = (
                        yaml.safe_load(raw)
                        if candidate.suffix in {".yaml", ".yml"}
                        else json.loads(raw)
                    )
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "rules" in data:
                        return data["rules"]
                except Exception as exc:
                    logger.debug("Parse failed for %s: %s", candidate, exc)
    return None


def fetch_rules(*, offline: bool = False) -> RuleSource:
    """
    Try to fetch rules from ``mgechev/skills-best-practices``.

    Falls back to :data:`BASELINE_RULES` if the remote is unreachable or the
    parse step fails.
    """
    if offline:
        logger.info("Offline mode: using built-in baseline rules.")
        return RuleSource(BASELINE_RULES)

    sha = _get_remote_sha(BEST_PRACTICES_REPO)
    if sha is None:
        logger.warning("Could not reach %s; using built-in baseline rules.", BEST_PRACTICES_URL)
        return RuleSource(BASELINE_RULES)

    external_rules = _clone_and_parse(BEST_PRACTICES_REPO, sha)
    if external_rules is None:
        logger.warning(
            "Fetched %s (sha=%s) but found no parseable rule file; "
            "augmenting built-in rules with remote SHA for reproducibility.",
            BEST_PRACTICES_URL,
            sha,
        )
        return RuleSource(
            BASELINE_RULES,
            source_url=BEST_PRACTICES_URL,
            commit_sha=sha,
            is_baseline=True,
        )

    # Merge: remote rules take precedence over baseline by id
    merged = {r["id"]: r for r in BASELINE_RULES}
    for rule in external_rules:
        if isinstance(rule, dict) and "id" in rule:
            merged[rule["id"]] = rule

    logger.info(
        "Rules loaded from %s @ %s (%d rules).",
        BEST_PRACTICES_URL,
        sha[:12],
        len(merged),
    )
    return RuleSource(
        list(merged.values()),
        source_url=BEST_PRACTICES_URL,
        commit_sha=sha,
        is_baseline=False,
    )
