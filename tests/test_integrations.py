"""Tests for praxis/integrations/ — all subprocess calls mocked."""

from __future__ import annotations

import json
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from praxis.config import Config
from praxis.integrations import (
    INTEGRATION_SCHEMAS,
    INTEGRATION_IMPLEMENTATIONS,
    get_integration_schemas,
)
from praxis.integrations.github import execute_github, _run_gh
from praxis.integrations.codebase import execute_analyze
from praxis.integrations.testrunner import execute_testrunner
from praxis.integrations.dependencies import execute_dependencies
from praxis.integrations.web import (
    execute_web_research,
    _strip_html,
    _extract_domain,
    _check_domain,
    BRAVE_API_DOMAIN,
)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        workspace_root=tmp_path,
        memory_root=tmp_path / ".praxis" / "memory",
        hook_path=tmp_path / ".claude" / "hooks" / "escalation-boundary.py",
        allowed_domains=frozenset(),
    )


# ---------- Registry tests ----------


class TestRegistry:
    def test_all_schemas_registered(self):
        assert set(INTEGRATION_SCHEMAS.keys()) == {
            "GitHub", "Analyze", "TestRunner", "Dependencies", "WebResearch"
        }

    def test_all_implementations_registered(self):
        assert set(INTEGRATION_IMPLEMENTATIONS.keys()) == {
            "GitHub", "Analyze", "TestRunner", "Dependencies", "WebResearch"
        }

    def test_schema_format(self):
        for name, schema in INTEGRATION_SCHEMAS.items():
            assert schema["name"] == name
            assert "description" in schema
            assert "input_schema" in schema
            assert schema["input_schema"]["type"] == "object"
            assert "action" in schema["input_schema"]["properties"]

    def test_get_integration_schemas_all(self):
        schemas = get_integration_schemas()
        assert len(schemas) == 5

    def test_get_integration_schemas_filtered(self):
        schemas = get_integration_schemas(["GitHub", "TestRunner"])
        assert len(schemas) == 2
        names = {s["name"] for s in schemas}
        assert names == {"GitHub", "TestRunner"}

    def test_get_integration_schemas_unknown_ignored(self):
        schemas = get_integration_schemas(["GitHub", "NoSuchTool"])
        assert len(schemas) == 1


# ---------- GitHub integration ----------


class TestGitHub:
    @patch("shutil.which", return_value=None)
    def test_gh_not_installed(self, mock_which, config):
        result = execute_github({"action": "pr_list"}, config)
        assert "not installed" in result
        assert "cli.github.com" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_pr_list(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"number":1,"title":"Fix bug"}]',
            stderr="",
        )
        result = execute_github({"action": "pr_list"}, config)
        assert "Fix bug" in result
        cmd = mock_run.call_args[0][0]
        assert "pr" in cmd and "list" in cmd

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_pr_list_with_state_and_limit(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        execute_github({"action": "pr_list", "state": "closed", "limit": 5}, config)
        cmd = mock_run.call_args[0][0]
        assert "--state" in cmd
        idx = cmd.index("--state")
        assert cmd[idx + 1] == "closed"
        assert "--limit" in cmd
        idx = cmd.index("--limit")
        assert cmd[idx + 1] == "5"

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_pr_view(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"number":42,"title":"My PR"}', stderr=""
        )
        result = execute_github({"action": "pr_view", "number": 42}, config)
        assert "My PR" in result

    def test_pr_view_missing_number(self, config):
        with patch("shutil.which", return_value="/usr/bin/gh"):
            result = execute_github({"action": "pr_view"}, config)
            assert "required" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_issue_list(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        result = execute_github({"action": "issue_list"}, config)
        cmd = mock_run.call_args[0][0]
        assert "issue" in cmd and "list" in cmd

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_issue_view(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0, stdout='{"number":7}', stderr=""
        )
        result = execute_github({"action": "issue_view", "number": 7}, config)
        assert "7" in result

    def test_issue_view_missing_number(self, config):
        with patch("shutil.which", return_value="/usr/bin/gh"):
            result = execute_github({"action": "issue_view"}, config)
            assert "required" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_pr_diff(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="diff --git a/f.py b/f.py", stderr=""
        )
        result = execute_github({"action": "pr_diff", "number": 1}, config)
        assert "diff" in result

    def test_pr_diff_missing_number(self, config):
        with patch("shutil.which", return_value="/usr/bin/gh"):
            result = execute_github({"action": "pr_diff"}, config)
            assert "required" in result

    def test_unknown_action(self, config):
        result = execute_github({"action": "bogus"}, config)
        assert "unknown" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_auth_failure(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="To get started with GitHub CLI, please run: gh auth login",
        )
        result = execute_github({"action": "pr_list"}, config)
        assert "not authenticated" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30))
    def test_timeout(self, mock_run, mock_which, config):
        result = execute_github({"action": "pr_list"}, config)
        assert "timed out" in result

    @patch("shutil.which", return_value="/usr/bin/gh")
    @patch("subprocess.run")
    def test_generic_error(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="repository not found"
        )
        result = execute_github({"action": "pr_list"}, config)
        assert "repository not found" in result


# ---------- Codebase analysis ----------


class TestAnalyze:
    @patch("shutil.which", return_value=None)
    def test_coverage_not_installed(self, mock_which, config):
        result = execute_analyze({"action": "coverage"}, config)
        assert "not installed" in result
        assert "coverage" in result

    @patch("shutil.which", return_value="/usr/bin/coverage")
    @patch("subprocess.run")
    def test_coverage_success(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Name    Stmts   Miss  Cover\nfoo.py  10      2     80%",
            stderr="",
        )
        result = execute_analyze({"action": "coverage"}, config)
        assert "80%" in result

    @patch("shutil.which", return_value="/usr/bin/coverage")
    @patch("subprocess.run")
    def test_coverage_no_data(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="No data to report"
        )
        result = execute_analyze({"action": "coverage"}, config)
        assert "no coverage data" in result

    @patch("shutil.which", return_value=None)
    def test_complexity_not_installed(self, mock_which, config):
        result = execute_analyze({"action": "complexity"}, config)
        assert "radon" in result
        assert "not installed" in result

    @patch("shutil.which", return_value="/usr/bin/radon")
    @patch("subprocess.run")
    def test_complexity_success(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="foo.py\n    F 1:0 my_func - A (2)",
            stderr="",
        )
        result = execute_analyze({"action": "complexity"}, config)
        assert "my_func" in result

    @patch("shutil.which", return_value=None)
    def test_lint_not_installed(self, mock_which, config):
        result = execute_analyze({"action": "lint"}, config)
        assert "pylint" in result
        assert "not installed" in result

    @patch("shutil.which", return_value="/usr/bin/pylint")
    @patch("subprocess.run")
    def test_lint_success(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=4,  # pylint uses non-zero for warnings
            stdout="foo.py:1: W0611: Unused import os",
            stderr="",
        )
        result = execute_analyze({"action": "lint"}, config)
        assert "Unused import" in result

    @patch("shutil.which", return_value="/usr/bin/pylint")
    @patch("subprocess.run")
    def test_lint_clean(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = execute_analyze({"action": "lint"}, config)
        assert "no issues found" in result

    def test_unknown_action(self, config):
        result = execute_analyze({"action": "bogus"}, config)
        assert "unknown" in result

    @patch("shutil.which", return_value="/usr/bin/coverage")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("coverage", 60))
    def test_coverage_timeout(self, mock_run, mock_which, config):
        result = execute_analyze({"action": "coverage"}, config)
        assert "timed out" in result

    @patch("shutil.which", return_value="/usr/bin/radon")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("radon", 60))
    def test_complexity_timeout(self, mock_run, mock_which, config):
        result = execute_analyze({"action": "complexity"}, config)
        assert "timed out" in result

    @patch("shutil.which", return_value="/usr/bin/pylint")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pylint", 120))
    def test_lint_timeout(self, mock_run, mock_which, config):
        result = execute_analyze({"action": "lint"}, config)
        assert "timed out" in result

    @patch("shutil.which", return_value="/usr/bin/radon")
    @patch("subprocess.run")
    def test_complexity_with_path(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="(no output)", stderr="")
        execute_analyze({"action": "complexity", "path": "praxis/"}, config)
        cmd = mock_run.call_args[0][0]
        assert "praxis/" in cmd


# ---------- Test runner ----------


class TestTestRunner:
    @patch("shutil.which", return_value=None)
    def test_pytest_not_installed(self, mock_which, config):
        result = execute_testrunner({"action": "run"}, config)
        assert "not installed" in result
        assert "pytest" in result

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_run_default(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="5 passed in 0.5s",
            stderr="",
        )
        result = execute_testrunner({"action": "run"}, config)
        assert "5 passed" in result
        cmd = mock_run.call_args[0][0]
        assert "tests/" in cmd

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_run_custom_path(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        execute_testrunner({"action": "run", "path": "tests/test_foo.py"}, config)
        cmd = mock_run.call_args[0][0]
        assert "tests/test_foo.py" in cmd

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_run_with_marker(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        execute_testrunner({"action": "run", "marker": "not slow"}, config)
        cmd = mock_run.call_args[0][0]
        assert "-m" in cmd
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "not slow"

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_run_with_keyword(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        execute_testrunner({"action": "run", "keyword": "test_foo"}, config)
        cmd = mock_run.call_args[0][0]
        assert "-k" in cmd
        idx = cmd.index("-k")
        assert cmd[idx + 1] == "test_foo"

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_run_failed(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="1 passed", stderr=""
        )
        result = execute_testrunner({"action": "run_failed"}, config)
        cmd = mock_run.call_args[0][0]
        assert "--lf" in cmd

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run")
    def test_test_failures(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="FAILED test_foo.py::test_bar",
            stderr="",
        )
        result = execute_testrunner({"action": "run"}, config)
        assert "FAILED" in result
        assert "Exit code: 1" in result

    def test_unknown_action(self, config):
        with patch("shutil.which", return_value="/usr/bin/pytest"):
            result = execute_testrunner({"action": "bogus"}, config)
            assert "unknown" in result

    @patch("shutil.which", return_value="/usr/bin/pytest")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pytest", 300))
    def test_timeout(self, mock_run, mock_which, config):
        result = execute_testrunner({"action": "run"}, config)
        assert "timed out" in result


# ---------- Dependencies ----------


class TestDependencies:
    @patch("shutil.which", return_value="/usr/bin/pip")
    @patch("subprocess.run")
    def test_outdated(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='[{"name":"requests","version":"2.28.0","latest_version":"2.31.0"}]',
            stderr="",
        )
        result = execute_dependencies({"action": "outdated"}, config)
        assert "requests" in result
        cmd = mock_run.call_args[0][0]
        assert "--outdated" in cmd
        assert "--format=json" in cmd

    @patch("shutil.which", return_value=None)
    def test_pip_not_found(self, mock_which, config):
        result = execute_dependencies({"action": "outdated"}, config)
        assert "pip not found" in result

    @patch("shutil.which", return_value="/usr/bin/pip")
    @patch("subprocess.run")
    def test_outdated_error(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="something broke"
        )
        result = execute_dependencies({"action": "outdated"}, config)
        assert "something broke" in result

    @patch("shutil.which", return_value=None)
    def test_audit_not_installed(self, mock_which, config):
        result = execute_dependencies({"action": "audit"}, config)
        assert "pip-audit" in result
        assert "not installed" in result

    @patch("shutil.which", return_value="/usr/bin/pip-audit")
    @patch("subprocess.run")
    def test_audit_clean(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"dependencies":[],"vulnerabilities":[]}',
            stderr="",
        )
        result = execute_dependencies({"action": "audit"}, config)
        assert "vulnerabilities" in result

    @patch("shutil.which", return_value="/usr/bin/pip-audit")
    @patch("subprocess.run")
    def test_audit_with_vulns(self, mock_run, mock_which, config):
        mock_run.return_value = MagicMock(
            returncode=1,  # non-zero = vulns found
            stdout='{"vulnerabilities":[{"name":"flask","id":"CVE-2023-1234"}]}',
            stderr="",
        )
        result = execute_dependencies({"action": "audit"}, config)
        assert "CVE-2023-1234" in result

    def test_unknown_action(self, config):
        result = execute_dependencies({"action": "bogus"}, config)
        assert "unknown" in result

    @patch("shutil.which", return_value="/usr/bin/pip")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip", 60))
    def test_outdated_timeout(self, mock_run, mock_which, config):
        result = execute_dependencies({"action": "outdated"}, config)
        assert "timed out" in result

    @patch("shutil.which", return_value="/usr/bin/pip-audit")
    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pip-audit", 120))
    def test_audit_timeout(self, mock_run, mock_which, config):
        result = execute_dependencies({"action": "audit"}, config)
        assert "timed out" in result


# ---------- Orchestrator integration ----------


class TestOrchestratorIntegration:
    """Verify integration tools are wired into the orchestrator dispatch."""

    def test_orchestrator_dispatches_integration_tool(self, workspace):
        """Integration tools are reachable via _execute_with_hook."""
        from praxis.orchestrator import Orchestrator
        from tests.conftest import FakeClient, FakeResponse, FakeTextBlock
        from praxis.runtime.claude_code import ClaudeCodeRuntime

        ws_config = Config(
            workspace_root=workspace,
            memory_root=workspace / ".praxis" / "memory",
            hook_path=workspace / ".claude" / "hooks" / "escalation-boundary.py",
            allowed_domains=frozenset(),
        )
        client = FakeClient([FakeResponse(content=[FakeTextBlock("ok")])])
        runtime = ClaudeCodeRuntime(client)
        orch = Orchestrator(runtime, ws_config)

        with patch("shutil.which", return_value=None):
            result = orch._execute_with_hook("GitHub", {"action": "pr_list"})
        assert "not installed" in result  # proves dispatch reached github.py

    def test_unknown_tool_still_errors(self, workspace):
        from praxis.orchestrator import Orchestrator
        from tests.conftest import FakeClient, FakeResponse, FakeTextBlock
        from praxis.runtime.claude_code import ClaudeCodeRuntime

        ws_config = Config(
            workspace_root=workspace,
            memory_root=workspace / ".praxis" / "memory",
            hook_path=workspace / ".claude" / "hooks" / "escalation-boundary.py",
            allowed_domains=frozenset(),
        )
        client = FakeClient([FakeResponse(content=[FakeTextBlock("ok")])])
        runtime = ClaudeCodeRuntime(client)
        orch = Orchestrator(runtime, ws_config)

        result = orch._execute_with_hook("NoSuchTool", {})
        assert "unknown tool" in result


# ---------- Secret redaction ----------


# ---------- Web research ----------


class TestWebResearchHelpers:
    def test_strip_html_basic(self):
        html = "<h1>Title</h1><p>Hello <b>world</b></p>"
        text = _strip_html(html)
        assert "Title" in text
        assert "Hello world" in text
        assert "<" not in text

    def test_strip_html_scripts_removed(self):
        html = "<p>Before</p><script>alert('xss')</script><p>After</p>"
        text = _strip_html(html)
        assert "Before" in text
        assert "After" in text
        assert "alert" not in text

    def test_strip_html_style_removed(self):
        html = "<style>.foo{color:red}</style><p>Content</p>"
        text = _strip_html(html)
        assert "Content" in text
        assert "color" not in text

    def test_extract_domain(self):
        assert _extract_domain("https://example.com/path") == "example.com"
        assert _extract_domain("http://sub.example.com:8080/p") == "sub.example.com"
        assert _extract_domain("not-a-url") == ""

    def test_check_domain_allowed(self, config):
        cfg = Config(
            workspace_root=config.workspace_root,
            memory_root=config.memory_root,
            hook_path=config.hook_path,
            allowed_domains=frozenset({"example.com"}),
        )
        assert _check_domain("example.com", cfg) is None

    def test_check_domain_blocked(self, config):
        result = _check_domain("evil.com", config)
        assert result is not None
        assert "not in PRAXIS_ALLOWED_DOMAINS" in result

    def test_check_domain_empty(self, config):
        result = _check_domain("", config)
        assert "could not extract domain" in result


class TestWebResearchSearch:
    def _config_with_domains(self, config, domains):
        return Config(
            workspace_root=config.workspace_root,
            memory_root=config.memory_root,
            hook_path=config.hook_path,
            allowed_domains=frozenset(domains),
        )

    def test_missing_api_key(self, config, monkeypatch):
        monkeypatch.delenv("PRAXIS_WEB_SEARCH_API_KEY", raising=False)
        result = execute_web_research(
            {"action": "search", "query": "test"}, config
        )
        assert "PRAXIS_WEB_SEARCH_API_KEY not set" in result
        assert "brave.com" in result

    def test_search_domain_not_allowed(self, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        result = execute_web_research(
            {"action": "search", "query": "test"}, config
        )
        assert "not in PRAXIS_ALLOWED_DOMAINS" in result

    def test_search_missing_query(self, config):
        result = execute_web_research({"action": "search"}, config)
        assert "'query' is required" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_success(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "web": {
                "results": [
                    {"title": "Python Docs", "url": "https://python.org", "description": "Official docs"},
                    {"title": "PyPI", "url": "https://pypi.org", "description": "Package index"},
                ]
            }
        }).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "search", "query": "python", "n": 2}, cfg
        )
        assert "Python Docs" in result
        assert "python.org" in result
        assert "PyPI" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_no_results(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"web": {"results": []}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "search", "query": "xyznonexistent"}, cfg
        )
        assert "No results found" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_http_error(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        err = urllib.error.HTTPError(
            "https://api.search.brave.com/res/v1/web/search",
            401, "Unauthorized", {}, None
        )
        mock_urlopen.side_effect = err

        result = execute_web_research(
            {"action": "search", "query": "test"}, cfg
        )
        assert "401" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_url_error(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        mock_urlopen.side_effect = urllib.error.URLError("DNS lookup failed")

        result = execute_web_research(
            {"action": "search", "query": "test"}, cfg
        )
        assert "could not reach" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_timeout(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        mock_urlopen.side_effect = TimeoutError()

        result = execute_web_research(
            {"action": "search", "query": "test"}, cfg
        )
        assert "timed out" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_search_n_clamped(self, mock_urlopen, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "test-key")
        cfg = self._config_with_domains(config, {BRAVE_API_DOMAIN})

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"web": {"results": []}}).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        # n=100 should be clamped to 20
        execute_web_research(
            {"action": "search", "query": "test", "n": 100}, cfg
        )
        call_args = mock_urlopen.call_args[0][0]
        assert "count=20" in call_args.full_url


class TestWebResearchFetch:
    def _config_with_domains(self, config, domains):
        return Config(
            workspace_root=config.workspace_root,
            memory_root=config.memory_root,
            hook_path=config.hook_path,
            allowed_domains=frozenset(domains),
        )

    def test_fetch_domain_not_allowed(self, config):
        result = execute_web_research(
            {"action": "fetch", "url": "https://evil.com/page"}, config
        )
        assert "not in PRAXIS_ALLOWED_DOMAINS" in result

    def test_fetch_missing_url(self, config):
        result = execute_web_research({"action": "fetch"}, config)
        assert "'url' is required" in result

    def test_fetch_bad_scheme(self, config):
        cfg = self._config_with_domains(config, {"example.com"})
        result = execute_web_research(
            {"action": "fetch", "url": "ftp://example.com/file"}, cfg
        )
        assert "http://" in result or "https://" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_html_success(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"docs.python.org"})

        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b"<html><body><h1>Python</h1><p>Hello world</p></body></html>"
        )
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "fetch", "url": "https://docs.python.org/3/"}, cfg
        )
        assert "Fetched" in result
        assert "Python" in result
        assert "Hello world" in result
        assert "<html>" not in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_plain_text(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"Just plain text content"
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/file.txt"}, cfg
        )
        assert "Just plain text content" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_json_content(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"api.example.com"})

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"key": "value"}'
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "fetch", "url": "https://api.example.com/data"}, cfg
        )
        assert '"key": "value"' in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_non_text_rejected(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "image/png"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/img.png"}, cfg
        )
        assert "non-text content type" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_truncated(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})

        mock_resp = MagicMock()
        mock_resp.read.return_value = ("x" * 10000).encode()
        mock_resp.headers = {"Content-Type": "text/plain"}
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/big", "max_chars": 100},
            cfg,
        )
        # Content should be truncated
        fetched_line = result.split("\n")[0]
        assert "100 chars" in fetched_line

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_http_error(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://example.com", 404, "Not Found", {}, None
        )
        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/missing"}, cfg
        )
        assert "404" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_url_error(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/"}, cfg
        )
        assert "could not fetch" in result

    @patch("praxis.integrations.web.urllib.request.urlopen")
    def test_fetch_timeout(self, mock_urlopen, config):
        cfg = self._config_with_domains(config, {"example.com"})
        mock_urlopen.side_effect = TimeoutError()
        result = execute_web_research(
            {"action": "fetch", "url": "https://example.com/"}, cfg
        )
        assert "timed out" in result


class TestWebResearchDispatch:
    def test_unknown_action(self, config):
        result = execute_web_research({"action": "bogus"}, config)
        assert "unknown" in result


class TestSecretRedaction:
    def test_github_token_redacted(self, config, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret123")
        with patch("shutil.which", return_value="/usr/bin/gh"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="token is ghp_secret123 here",
                    stderr="",
                )
                result = execute_github({"action": "pr_list"}, config)
                assert "ghp_secret123" not in result
                assert "[REDACTED]" in result

    def test_web_search_key_redacted(self, config, monkeypatch):
        monkeypatch.setenv("PRAXIS_WEB_SEARCH_API_KEY", "BSAsecretkey123")
        cfg = Config(
            workspace_root=config.workspace_root,
            memory_root=config.memory_root,
            hook_path=config.hook_path,
            allowed_domains=frozenset({"example.com"}),
        )
        with patch("praxis.integrations.web.urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"The key BSAsecretkey123 leaked"
            mock_resp.headers = {"Content-Type": "text/plain"}
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = execute_web_research(
                {"action": "fetch", "url": "https://example.com/page"}, cfg
            )
            assert "BSAsecretkey123" not in result
            assert "[REDACTED]" in result
