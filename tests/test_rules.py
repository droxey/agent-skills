"""
Tests for rules.py – rule fetching with mocked network calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from skillsctl.rules import (
    BASELINE_RULES,
    BEST_PRACTICES_REPO,
    BEST_PRACTICES_URL,
    RuleSource,
    _get_remote_sha,
    fetch_rules,
)

# ---------------------------------------------------------------------------
# RuleSource
# ---------------------------------------------------------------------------


class TestRuleSource:
    def test_baseline_defaults(self) -> None:
        rs = RuleSource(BASELINE_RULES)
        assert rs.is_baseline is True
        assert rs.commit_sha == "N/A"
        assert rs.source_url == "(built-in)"
        assert len(rs.rules) == len(BASELINE_RULES)

    def test_as_dict_keys(self) -> None:
        rs = RuleSource(BASELINE_RULES)
        d = rs.as_dict()
        assert "source_url" in d
        assert "commit_sha" in d
        assert "fetched_at" in d
        assert "is_baseline" in d
        assert "rule_count" in d

    def test_rule_count_matches(self) -> None:
        rs = RuleSource(BASELINE_RULES)
        assert rs.as_dict()["rule_count"] == len(BASELINE_RULES)


# ---------------------------------------------------------------------------
# fetch_rules – offline mode
# ---------------------------------------------------------------------------


class TestFetchRulesOffline:
    def test_offline_returns_baseline(self) -> None:
        rs = fetch_rules(offline=True)
        assert rs.is_baseline is True
        assert rs.rules == BASELINE_RULES

    def test_offline_does_not_call_network(self) -> None:
        with patch("skillsctl.rules._get_remote_sha") as mock_sha:
            fetch_rules(offline=True)
            mock_sha.assert_not_called()


# ---------------------------------------------------------------------------
# fetch_rules – mocked network success
# ---------------------------------------------------------------------------


class TestFetchRulesOnline:
    def test_fallback_when_sha_unreachable(self) -> None:
        with patch("skillsctl.rules._get_remote_sha", return_value=None):
            rs = fetch_rules(offline=False)
        assert rs.is_baseline is True
        assert rs.rules == BASELINE_RULES

    def test_fallback_when_clone_fails(self) -> None:
        with (
            patch("skillsctl.rules._get_remote_sha", return_value="abc123"),
            patch("skillsctl.rules._clone_and_parse", return_value=None),
        ):
            rs = fetch_rules(offline=False)
        # Should still have baseline rules, but record the SHA
        assert rs.commit_sha == "abc123"
        assert rs.is_baseline is True

    def test_external_rules_merged(self) -> None:
        extra_rules = [
            {
                "id": "EXT001",
                "name": "external-rule",
                "severity": "info",
                "description": "An external rule.",
                "effort": "low",
                "fixable": False,
            }
        ]
        with (
            patch("skillsctl.rules._get_remote_sha", return_value="deadbeef"),
            patch("skillsctl.rules._clone_and_parse", return_value=extra_rules),
        ):
            rs = fetch_rules(offline=False)
        rule_ids = [r["id"] for r in rs.rules]
        assert "EXT001" in rule_ids
        # Baseline rules should still be present
        baseline_ids = {r["id"] for r in BASELINE_RULES}
        for bid in baseline_ids:
            assert bid in rule_ids

    def test_commit_sha_recorded_on_success(self) -> None:
        extra_rules = [
            {
                "id": "X001",
                "name": "x",
                "severity": "info",
                "description": "x",
                "effort": "low",
                "fixable": False,
            }
        ]
        with (
            patch("skillsctl.rules._get_remote_sha", return_value="cafebabe1234"),
            patch("skillsctl.rules._clone_and_parse", return_value=extra_rules),
        ):
            rs = fetch_rules(offline=False)
        assert rs.commit_sha == "cafebabe1234"
        assert rs.source_url == BEST_PRACTICES_URL
        assert rs.is_baseline is False

    def test_baseline_rule_overridden_by_external(self) -> None:
        overriding = [
            {
                "id": "FM001",  # same id as baseline
                "name": "overridden",
                "severity": "warning",  # changed severity
                "description": "External override.",
                "effort": "low",
                "fixable": True,
            }
        ]
        with (
            patch("skillsctl.rules._get_remote_sha", return_value="aaa"),
            patch("skillsctl.rules._clone_and_parse", return_value=overriding),
        ):
            rs = fetch_rules(offline=False)
        fm001 = next(r for r in rs.rules if r["id"] == "FM001")
        assert fm001["name"] == "overridden"


# ---------------------------------------------------------------------------
# _get_remote_sha – mocked subprocess
# ---------------------------------------------------------------------------


class TestGetRemoteSha:
    def test_returns_sha_on_success(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123def456\tHEAD\n"
        with patch("subprocess.run", return_value=mock_result):
            sha = _get_remote_sha(BEST_PRACTICES_REPO)
        assert sha == "abc123def456"

    def test_returns_none_on_nonzero(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            sha = _get_remote_sha(BEST_PRACTICES_REPO)
        assert sha is None

    def test_returns_none_on_exception(self) -> None:
        with patch("subprocess.run", side_effect=Exception("network error")):
            sha = _get_remote_sha(BEST_PRACTICES_REPO)
        assert sha is None
