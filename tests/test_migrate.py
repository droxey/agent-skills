"""
Tests for migrate.py – skill migration with dry-run and apply modes.
"""

from __future__ import annotations

from pathlib import Path

from skillsctl.migrate import (
    _domain_from_tags,
    _ensure_stable_id,
    run_migrate,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestDomainFromTags:
    def test_uses_first_tag(self) -> None:
        assert _domain_from_tags(["code-review", "quality"]) == "code-review"

    def test_empty_tags_returns_general(self) -> None:
        assert _domain_from_tags([]) == "general"

    def test_none_returns_general(self) -> None:
        assert _domain_from_tags(None) == "general"

    def test_normalises_tag(self) -> None:
        domain = _domain_from_tags(["My Tag!"])
        # Special chars replaced with hyphens; trailing hyphens stripped
        assert domain  # non-empty
        assert domain == domain.lower()
        assert " " not in domain


class TestEnsureStableId:
    def test_keeps_existing_id(self) -> None:
        fm = {"id": "existing-id", "name": "x"}
        result = _ensure_stable_id(fm, "owner/repo", "path/file.md")
        assert result["id"] == "existing-id"

    def test_generates_id_when_missing(self) -> None:
        fm = {"name": "x"}
        result = _ensure_stable_id(fm, "owner/repo", "path/file.md")
        assert "id" in result
        assert result["id"]

    def test_generates_id_when_empty_string(self) -> None:
        fm = {"id": "", "name": "x"}
        result = _ensure_stable_id(fm, "owner/repo", "path/file.md")
        assert result["id"]  # should be non-empty after generation


# ---------------------------------------------------------------------------
# run_migrate – dry-run
# ---------------------------------------------------------------------------


class TestRunMigrateDryRun:
    def _make_manifest(self, file_path: str, repo: str = "test/repo") -> dict:
        return {
            "candidates": [
                {
                    "repo": repo,
                    "path": Path(file_path).name,
                    "abs_path": file_path,
                    "content_hash": "abc",
                    "has_frontmatter": True,
                    "frontmatter": {},
                }
            ]
        }

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        manifest = self._make_manifest(str(FIXTURES / "good_skill.md"))
        report = run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=False,
            dry_run=True,
        )
        assert report["dry_run"] is True
        assert report["summary"]["applied"] == 0
        # No files should have been created
        assert not any(tmp_path.rglob("*.md"))

    def test_apply_writes_file(self, tmp_path: Path) -> None:
        # Copy fixture to tmp so we can overwrite the pointer
        src = tmp_path / "good_skill.md"
        src.write_text((FIXTURES / "good_skill.md").read_text())
        manifest = self._make_manifest(str(src))
        report = run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=True,
            dry_run=False,
            write_pointer=False,
        )
        assert report["applied"] is True
        assert report["summary"]["applied"] == 1

    def test_apply_creates_domain_directory(self, tmp_path: Path) -> None:
        src = tmp_path / "good_skill.md"
        src.write_text((FIXTURES / "good_skill.md").read_text())
        manifest = self._make_manifest(str(src))
        run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=True,
            dry_run=False,
            write_pointer=False,
        )
        # skills/code-review/ should exist
        domain_dirs = list((tmp_path / "skills").iterdir())
        assert len(domain_dirs) >= 1

    def test_apply_writes_pointer(self, tmp_path: Path) -> None:
        src = tmp_path / "good_skill.md"
        src.write_text((FIXTURES / "good_skill.md").read_text())
        manifest = self._make_manifest(str(src))
        run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=True,
            dry_run=False,
            write_pointer=True,
        )
        # Source file should now contain a pointer
        new_content = src.read_text()
        assert "migrated" in new_content.lower()

    def test_report_structure(self, tmp_path: Path) -> None:
        manifest = self._make_manifest(str(FIXTURES / "good_skill.md"))
        report = run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=False,
            dry_run=True,
        )
        assert "schema_version" in report
        assert "summary" in report
        assert "actions" in report

    def test_action_has_stable_id(self, tmp_path: Path) -> None:
        manifest = self._make_manifest(str(FIXTURES / "good_skill.md"))
        report = run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=False,
            dry_run=True,
        )
        for action in report["actions"]:
            assert "skill_id" in action
            assert action["skill_id"]  # non-empty

    def test_migrated_file_has_source_field(self, tmp_path: Path) -> None:

        src = tmp_path / "good_skill.md"
        src.write_text((FIXTURES / "good_skill.md").read_text())
        manifest = self._make_manifest(str(src), repo="test/repo")
        run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=True,
            dry_run=False,
            write_pointer=False,
        )
        # Find the migrated file
        migrated_files = list((tmp_path / "skills").rglob("*.md"))
        assert migrated_files
        content = migrated_files[0].read_text()
        assert "source:" in content
        assert "migrated_at:" in content

    def test_allow_delete_requires_apply(self, tmp_path: Path) -> None:
        """allow_delete without apply should not delete files."""
        src = tmp_path / "good_skill.md"
        src.write_text((FIXTURES / "good_skill.md").read_text())
        manifest = self._make_manifest(str(src))
        run_migrate(
            manifest,
            skills_root=tmp_path / "skills",
            apply=False,
            allow_delete=True,
            dry_run=True,
            write_pointer=False,
        )
        # Source file should still exist
        assert src.exists()
