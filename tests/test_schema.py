"""
Tests for schema.py – frontmatter parsing, validation, and ID generation.
"""

from __future__ import annotations

from skillsctl.schema import (
    build_stable_id,
    content_hash,
    extract_frontmatter,
    validate_frontmatter,
)

# ---------------------------------------------------------------------------
# extract_frontmatter
# ---------------------------------------------------------------------------


class TestExtractFrontmatter:
    def test_valid_frontmatter(self) -> None:
        content = "---\nid: my-skill\nname: Test\n---\nBody text."
        fm, body = extract_frontmatter(content)
        assert fm is not None
        assert fm["id"] == "my-skill"
        assert "Body text." in body

    def test_no_frontmatter(self) -> None:
        content = "# Just a heading\n\nSome text."
        fm, body = extract_frontmatter(content)
        assert fm is None
        assert body == content

    def test_empty_frontmatter(self) -> None:
        content = "---\n---\nBody."
        fm, body = extract_frontmatter(content)
        # yaml.safe_load of empty string returns None
        assert fm is None or fm == {}

    def test_invalid_yaml_in_frontmatter(self) -> None:
        content = "---\n: bad: yaml: {\n---\nBody."
        fm, body = extract_frontmatter(content)
        # Should not raise; returns None gracefully
        assert fm is None

    def test_fixture_good_skill(self) -> None:
        from pathlib import Path

        content = (Path(__file__).parent / "fixtures" / "good_skill.md").read_text()
        fm, body = extract_frontmatter(content)
        assert fm is not None
        assert fm["id"] == "code-review"
        assert "Code Review Assistant" in body


# ---------------------------------------------------------------------------
# validate_frontmatter
# ---------------------------------------------------------------------------


class TestValidateFrontmatter:
    def _valid_fm(self) -> dict:
        return {
            "id": "my-skill",
            "name": "My Skill",
            "description": "Does something useful.",
            "version": "1.0.0",
            "tags": ["general"],
        }

    def test_valid_passes(self) -> None:
        errors = validate_frontmatter(self._valid_fm())
        assert errors == []

    def test_missing_id(self) -> None:
        fm = self._valid_fm()
        del fm["id"]
        errors = validate_frontmatter(fm)
        assert any("id" in e for e in errors)

    def test_missing_name(self) -> None:
        fm = self._valid_fm()
        del fm["name"]
        errors = validate_frontmatter(fm)
        assert errors

    def test_bad_id_pattern(self) -> None:
        fm = self._valid_fm()
        fm["id"] = "BadID_with spaces"
        errors = validate_frontmatter(fm)
        assert any("id" in e for e in errors)

    def test_bad_version(self) -> None:
        fm = self._valid_fm()
        fm["version"] = "v2-invalid"
        errors = validate_frontmatter(fm)
        assert any("version" in e for e in errors)

    def test_empty_tags(self) -> None:
        fm = self._valid_fm()
        fm["tags"] = []
        errors = validate_frontmatter(fm)
        assert any("tags" in e for e in errors)

    def test_description_too_short(self) -> None:
        fm = self._valid_fm()
        fm["description"] = "Short"
        errors = validate_frontmatter(fm)
        assert any("description" in e for e in errors)

    def test_optional_fields_accepted(self) -> None:
        fm = self._valid_fm()
        fm["verification"] = "Run test suite."
        fm["tooling"] = {"models": ["gpt-4o"]}
        errors = validate_frontmatter(fm)
        assert errors == []

    def test_inputs_outputs_validated(self) -> None:
        fm = self._valid_fm()
        fm["inputs"] = [{"name": "x", "type": "string"}]
        fm["outputs"] = [{"name": "y", "type": "integer"}]
        errors = validate_frontmatter(fm)
        assert errors == []

    def test_inputs_missing_type(self) -> None:
        fm = self._valid_fm()
        fm["inputs"] = [{"name": "x"}]  # missing 'type'
        errors = validate_frontmatter(fm)
        assert errors


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_deterministic(self) -> None:
        assert content_hash("hello") == content_hash("hello")

    def test_different_inputs(self) -> None:
        assert content_hash("hello") != content_hash("world")

    def test_sha256_length(self) -> None:
        h = content_hash("test")
        assert len(h) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# build_stable_id
# ---------------------------------------------------------------------------


class TestBuildStableId:
    def test_basic(self) -> None:
        sid = build_stable_id("droxey/dotfiles", "prompts/code-review.md")
        assert sid == "droxey-dotfiles-prompts-code-review"

    def test_no_extension(self) -> None:
        sid = build_stable_id("owner/repo", "plain-name")
        assert sid == "owner-repo-plain-name"

    def test_uppercase_normalised(self) -> None:
        sid = build_stable_id("Owner/Repo", "Path/To/Skill.MD")
        assert sid == sid.lower()

    def test_special_chars_stripped(self) -> None:
        sid = build_stable_id("a/b", "some skill (v2).md")
        # Should not contain spaces or parens
        assert " " not in sid
        assert "(" not in sid
        assert ")" not in sid

    def test_kebab_case(self) -> None:
        sid = build_stable_id("x/y", "z.md")
        # Should only contain lowercase letters, digits, and hyphens
        import re

        assert re.match(r"^[a-z0-9-]+$", sid)
