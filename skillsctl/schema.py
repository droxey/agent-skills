"""
JSON Schema definition and validation for skill YAML frontmatter.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

import jsonschema
import yaml

# ---------------------------------------------------------------------------
# Canonical JSON Schema for skill frontmatter
# ---------------------------------------------------------------------------

SKILL_FRONTMATTER_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://github.com/droxey/agent-skills/schemas/skill-frontmatter.json",
    "title": "SkillFrontmatter",
    "description": "YAML frontmatter for a skill/prompt Markdown file.",
    "type": "object",
    "required": ["id", "name", "description", "version", "tags"],
    "additionalProperties": True,
    "properties": {
        "id": {
            "type": "string",
            "description": "Stable, URL-safe identifier (kebab-case).",
            "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$",
        },
        "name": {
            "type": "string",
            "description": "Human-readable display name.",
            "minLength": 1,
        },
        "description": {
            "type": "string",
            "description": "One-sentence description of what the skill does.",
            "minLength": 10,
        },
        "version": {
            "type": "string",
            "description": "Semantic version string (e.g. '1.0.0').",
            "pattern": r"^\d+\.\d+(\.\d+)?(-[a-zA-Z0-9.]+)?$",
        },
        "tags": {
            "type": "array",
            "description": "Taxonomy tags for discovery and routing.",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "uniqueItems": True,
        },
        "inputs": {
            "type": "array",
            "description": "Declared input variables consumed by the skill.",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                    "required": {"type": "boolean"},
                },
            },
        },
        "outputs": {
            "type": "array",
            "description": "Declared output variables produced by the skill.",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "tooling": {
            "type": "object",
            "description": "Tooling / model constraints required by the skill.",
            "properties": {
                "models": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "min_context_tokens": {"type": "integer", "minimum": 0},
            },
        },
        "verification": {
            "type": "string",
            "description": "Guidance on how to verify the skill produces correct output.",
        },
        "source": {
            "type": "string",
            "description": "Original repository URL this skill was migrated from.",
        },
        "migrated_at": {
            "type": "string",
            "description": "ISO-8601 timestamp when migration occurred.",
        },
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def extract_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """
    Parse YAML frontmatter from a Markdown file.

    Returns ``(frontmatter_dict, body)`` where body is the content after the
    closing ``---`` delimiter.  If no frontmatter is found, returns
    ``(None, content)``.
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, content
    raw_yaml = m.group(1)
    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return None, content
    body = content[m.end() :]
    return data, body


def content_hash(content: str) -> str:
    """Return a stable SHA-256 hex digest for *content*."""
    return hashlib.sha256(content.encode()).hexdigest()


def validate_frontmatter(data: dict[str, Any]) -> list[str]:
    """
    Validate *data* against SKILL_FRONTMATTER_SCHEMA.

    Returns a list of human-readable error strings (empty → valid).
    """
    validator = jsonschema.Draft7Validator(SKILL_FRONTMATTER_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    messages: list[str] = []
    for err in errors:
        path = ".".join(str(p) for p in err.absolute_path) if err.absolute_path else "(root)"
        messages.append(f"{path}: {err.message}")
    return messages


def build_stable_id(repo: str, relative_path: str) -> str:
    """
    Derive a stable, deterministic skill ID from *repo* and *relative_path*.

    The result is a kebab-case string like ``droxey-dotfiles-prompts-code-review``.
    """
    parts = [repo.replace("/", "-"), relative_path]
    raw = "-".join(parts)
    # strip extension
    raw = re.sub(r"\.[^.]+$", "", raw)
    # normalise to kebab
    raw = re.sub(r"[^a-z0-9]+", "-", raw.lower())
    raw = raw.strip("-")
    return raw
