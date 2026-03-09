"""
Tests for scan.py – candidate detection heuristics and local scanning.
"""

from __future__ import annotations

from pathlib import Path

from skillsctl.scan import _is_candidate, _scan_directory, run_scan

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _is_candidate
# ---------------------------------------------------------------------------


class TestIsCandidate:
    def test_name_pattern_prompt(self, tmp_path: Path) -> None:
        f = tmp_path / "my-prompt.md"
        f.write_text("Some content")
        assert _is_candidate(f)

    def test_name_pattern_skill(self, tmp_path: Path) -> None:
        f = tmp_path / "my-skill.md"
        f.write_text("Some content")
        assert _is_candidate(f)

    def test_dir_pattern_prompts(self, tmp_path: Path) -> None:
        d = tmp_path / "prompts"
        d.mkdir()
        f = d / "anything.md"
        f.write_text("content")
        assert _is_candidate(f)

    def test_dir_pattern_agents(self, tmp_path: Path) -> None:
        d = tmp_path / "agents"
        d.mkdir()
        f = d / "file.md"
        f.write_text("content")
        assert _is_candidate(f)

    def test_non_matching_extension_rejected(self, tmp_path: Path) -> None:
        f = tmp_path / "image.png"
        f.write_text("not a skill")
        assert not _is_candidate(f)

    def test_non_matching_name_and_dir(self, tmp_path: Path) -> None:
        f = tmp_path / "regular-file.md"
        f.write_text("hello world")
        # No content signals, no dir/name patterns
        assert not _is_candidate(f, content="hello world")

    def test_content_signals(self, tmp_path: Path) -> None:
        f = tmp_path / "misc.md"
        content = "You are a helpful assistant.\nAct as a code reviewer."
        assert _is_candidate(f, content=content)

    def test_frontmatter_signal(self, tmp_path: Path) -> None:
        f = tmp_path / "notes.md"
        content = "---\nfoo: bar\n---\nYou are an assistant."
        # Has frontmatter + "you are" = 2 signals
        assert _is_candidate(f, content=content)


# ---------------------------------------------------------------------------
# _scan_directory
# ---------------------------------------------------------------------------


class TestScanDirectory:
    def test_finds_skill_files(self) -> None:
        results = _scan_directory(FIXTURES, "test-repo")
        paths = [r["path"] for r in results]
        # All fixture files should be discovered
        assert any("good_skill" in p for p in paths)
        assert any("no_frontmatter" in p for p in paths)

    def test_result_structure(self) -> None:
        results = _scan_directory(FIXTURES, "test-repo")
        assert len(results) > 0
        for r in results:
            assert "repo" in r
            assert "path" in r
            assert "abs_path" in r
            assert "content_hash" in r
            assert "has_frontmatter" in r
            assert "frontmatter" in r

    def test_has_frontmatter_flag(self) -> None:
        results = _scan_directory(FIXTURES, "test-repo")
        by_name = {Path(r["path"]).name: r for r in results}
        assert by_name["good_skill.md"]["has_frontmatter"] is True
        assert by_name["no_frontmatter.md"]["has_frontmatter"] is False

    def test_content_hash_stable(self) -> None:
        r1 = _scan_directory(FIXTURES, "test-repo")
        r2 = _scan_directory(FIXTURES, "test-repo")
        hashes1 = {r["path"]: r["content_hash"] for r in r1}
        hashes2 = {r["path"]: r["content_hash"] for r in r2}
        assert hashes1 == hashes2

    def test_ignores_git_dir(self, tmp_path: Path) -> None:
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")
        (git_dir / "prompt.md").write_text("should be ignored")
        real_file = tmp_path / "prompts" / "skill.md"
        real_file.parent.mkdir()
        real_file.write_text("real skill content")
        results = _scan_directory(tmp_path, "test")
        abs_paths = [r["abs_path"] for r in results]
        assert not any(".git" in p for p in abs_paths)
        assert any("skill.md" in p for p in abs_paths)


# ---------------------------------------------------------------------------
# run_scan – local paths
# ---------------------------------------------------------------------------


class TestRunScanLocal:
    def test_scan_local_path(self) -> None:
        manifest = run_scan([], local_paths=[str(FIXTURES)], dry_run=True)
        assert len(manifest["candidates"]) > 0
        assert manifest["sources"][0]["type"] == "local"

    def test_manifest_structure(self) -> None:
        manifest = run_scan([], local_paths=[str(FIXTURES)], dry_run=True)
        assert "schema_version" in manifest
        assert "created_at" in manifest
        assert "sources" in manifest
        assert "candidates" in manifest

    def test_nonexistent_local_path_skipped(self) -> None:
        manifest = run_scan([], local_paths=["/nonexistent/path"], dry_run=True)
        assert manifest["candidates"] == []

    def test_json_output(self, tmp_path: Path) -> None:
        import json

        out = tmp_path / "manifest.json"
        run_scan([], local_paths=[str(FIXTURES)], output_path=str(out), dry_run=True)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "candidates" in data
