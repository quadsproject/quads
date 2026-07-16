import os

import pytest

from quads.tools.conf_check import (
    CheckFinding,
    ConfCheckResult,
    check_default_values,
    check_missing_files,
    check_yaml_syntax,
    find_duplicate_keys,
    run_conf_check,
)


class TestCheckYamlSyntax:
    def test_valid_yaml_returns_none(self, tmp_path):
        f = tmp_path / "valid.yml"
        f.write_text("key: value\nnested:\n  a: 1\n")
        assert check_yaml_syntax(str(f)) is None

    def test_invalid_yaml_returns_finding(self, tmp_path):
        f = tmp_path / "bad.yml"
        f.write_text("key: value\nbad_indent:\n  a: 1\n b: 2\n")
        result = check_yaml_syntax(str(f))
        assert result is not None
        assert result.check_type == "syntax_error"
        assert result.severity == "error"
        assert result.file == "bad.yml"

    def test_unclosed_quote_detected(self, tmp_path):
        f = tmp_path / "quote.yml"
        f.write_text('key: "unclosed\n')
        result = check_yaml_syntax(str(f))
        assert result is not None
        assert result.check_type == "syntax_error"


class TestFindDuplicateKeys:
    def test_no_duplicates(self, tmp_path):
        f = tmp_path / "clean.yml"
        f.write_text("a: 1\nb: 2\nc: 3\n")
        assert find_duplicate_keys(str(f)) == []

    def test_top_level_duplicate(self, tmp_path):
        f = tmp_path / "dup.yml"
        f.write_text("a: 1\nb: 2\na: 3\n")
        results = find_duplicate_keys(str(f))
        assert len(results) == 1
        assert results[0].key == "a"
        assert results[0].check_type == "duplicate_key"
        assert results[0].severity == "warning"

    def test_nested_duplicate(self, tmp_path):
        f = tmp_path / "nested.yml"
        f.write_text("parent:\n  child: 1\n  child: 2\n")
        results = find_duplicate_keys(str(f))
        assert len(results) == 1
        assert results[0].key == "child"

    def test_invalid_yaml_returns_empty(self, tmp_path):
        f = tmp_path / "broken.yml"
        f.write_text('key: "unclosed\n')
        assert find_duplicate_keys(str(f)) == []


class TestCheckDefaultValues:
    def _write_configs(self, conf_dir, quads=None, plugins=None, oauth=None, selfservice=None):
        if quads:
            (conf_dir / "quads.yml").write_text(quads)
        if plugins:
            (conf_dir / "plugins.yml").write_text(plugins)
        if oauth:
            (conf_dir / "oauth.yml").write_text(oauth)
        if selfservice:
            (conf_dir / "selfservice.yml").write_text(selfservice)

    def test_default_domain_flagged(self, tmp_path):
        self._write_configs(tmp_path, quads="domain: example.com\nquads_url: https://real.lab.com\n")
        results = check_default_values(str(tmp_path))
        domain_findings = [f for f in results if f.key == "domain"]
        assert len(domain_findings) == 1
        assert domain_findings[0].severity == "error"

    def test_changed_domain_passes(self, tmp_path):
        self._write_configs(tmp_path, quads="domain: mylab.com\nquads_url: https://real.lab.com\n")
        results = check_default_values(str(tmp_path))
        domain_findings = [f for f in results if f.key == "domain"]
        assert len(domain_findings) == 0

    def test_nested_plugin_path(self, tmp_path):
        plugins_content = (
            "plugins:\n"
            "  foreman:\n"
            "    url: http://foreman.example.com/hosts/\n"
            "    api_url: https://foreman.example.com/api/v2\n"
            "  email:\n"
            "    smtp_host: mail.example.com\n"
        )
        self._write_configs(tmp_path, plugins=plugins_content)
        results = check_default_values(str(tmp_path))
        keys = {f.key for f in results}
        assert "plugins.foreman.url" in keys
        assert "plugins.foreman.api_url" in keys
        assert "plugins.email.smtp_host" in keys

    def test_changed_plugin_values_pass(self, tmp_path):
        plugins_content = (
            "plugins:\n"
            "  foreman:\n"
            "    url: http://foreman.mylab.com/hosts/\n"
            "    api_url: https://foreman.mylab.com/api/v2\n"
            "  email:\n"
            "    smtp_host: mail.mylab.com\n"
        )
        self._write_configs(tmp_path, plugins=plugins_content)
        results = check_default_values(str(tmp_path))
        plugin_findings = [f for f in results if f.file == "plugins.yml"]
        assert len(plugin_findings) == 0

    def test_oauth_domains_with_auth_required_is_error(self, tmp_path):
        self._write_configs(
            tmp_path,
            oauth="oauth_settings:\n  allowed_domains:\n    - 'example.com'\n",
            selfservice="require_auth_provider: true\n",
        )
        results = check_default_values(str(tmp_path))
        oauth_findings = [f for f in results if f.key == "oauth_settings.allowed_domains"]
        assert len(oauth_findings) == 1
        assert oauth_findings[0].severity == "error"

    def test_oauth_domains_without_auth_required_is_warning(self, tmp_path):
        self._write_configs(
            tmp_path,
            oauth="oauth_settings:\n  allowed_domains:\n    - 'example.com'\n",
            selfservice="require_auth_provider: false\n",
        )
        results = check_default_values(str(tmp_path))
        oauth_findings = [f for f in results if f.key == "oauth_settings.allowed_domains"]
        assert len(oauth_findings) == 1
        assert oauth_findings[0].severity == "warning"

    def test_oauth_domains_changed_passes(self, tmp_path):
        self._write_configs(
            tmp_path,
            oauth="oauth_settings:\n  allowed_domains:\n    - 'mylab.com'\n",
        )
        results = check_default_values(str(tmp_path))
        oauth_findings = [f for f in results if f.key == "oauth_settings.allowed_domains"]
        assert len(oauth_findings) == 0

    def test_missing_config_file_skipped(self, tmp_path):
        results = check_default_values(str(tmp_path))
        assert len(results) == 0


class TestCheckMissingFiles:
    def test_missing_files_detected(self, tmp_path):
        results = check_missing_files(str(tmp_path))
        assert len(results) == 5
        assert all(f.check_type == "missing_file" for f in results)
        assert all(f.severity == "error" for f in results)

    def test_all_files_present(self, tmp_path):
        for fname in ["quads.yml", "quadsweb.yml", "selfservice.yml", "plugins.yml", "oauth.yml"]:
            (tmp_path / fname).write_text("key: value\n")
        results = check_missing_files(str(tmp_path))
        assert len(results) == 0


class TestRunConfCheck:
    def _write_all_defaults(self, conf_dir):
        (conf_dir / "quads.yml").write_text("domain: example.com\n" "quads_url: https://quads.scalelab.example.com\n")
        (conf_dir / "quadsweb.yml").write_text("lab_name: test\n")
        (conf_dir / "selfservice.yml").write_text("require_auth_provider: false\n")
        (conf_dir / "plugins.yml").write_text(
            "plugins:\n"
            "  foreman:\n"
            "    url: http://foreman.example.com/hosts/\n"
            "    api_url: https://foreman.example.com/api/v2\n"
            "  email:\n"
            "    smtp_host: mail.example.com\n"
        )
        (conf_dir / "oauth.yml").write_text("oauth_settings:\n" "  allowed_domains:\n" "    - 'example.com'\n")

    def test_all_defaults_returns_findings(self, tmp_path):
        self._write_all_defaults(tmp_path)
        result = run_conf_check(str(tmp_path))
        assert not result.passed
        assert result.files_checked == 5
        default_findings = [f for f in result.findings if f.check_type == "default_value"]
        assert len(default_findings) == 6

    def test_clean_config_passes(self, tmp_path):
        (tmp_path / "quads.yml").write_text("domain: mylab.com\nquads_url: https://quads.mylab.com\n")
        (tmp_path / "quadsweb.yml").write_text("lab_name: test\n")
        (tmp_path / "selfservice.yml").write_text("require_auth_provider: false\n")
        (tmp_path / "plugins.yml").write_text(
            "plugins:\n"
            "  foreman:\n"
            "    url: http://foreman.mylab.com/hosts/\n"
            "    api_url: https://foreman.mylab.com/api/v2\n"
            "  email:\n"
            "    smtp_host: mail.mylab.com\n"
        )
        (tmp_path / "oauth.yml").write_text("oauth_settings:\n  allowed_domains:\n    - 'mylab.com'\n")
        result = run_conf_check(str(tmp_path))
        assert result.passed
        assert result.files_checked == 5

    def test_syntax_error_skips_further_checks(self, tmp_path):
        (tmp_path / "quads.yml").write_text('domain: "unclosed\n')
        (tmp_path / "quadsweb.yml").write_text("key: value\n")
        (tmp_path / "selfservice.yml").write_text("key: value\n")
        (tmp_path / "plugins.yml").write_text("key: value\n")
        (tmp_path / "oauth.yml").write_text("key: value\n")
        result = run_conf_check(str(tmp_path))
        syntax_findings = [f for f in result.findings if f.check_type == "syntax_error"]
        assert len(syntax_findings) == 1
        assert syntax_findings[0].file == "quads.yml"

    def test_mixed_results(self, tmp_path):
        (tmp_path / "quads.yml").write_text("domain: example.com\nquads_url: https://quads.mylab.com\n")
        (tmp_path / "quadsweb.yml").write_text("key: value\n")
        (tmp_path / "selfservice.yml").write_text("require_auth_provider: false\n")
        (tmp_path / "plugins.yml").write_text(
            "plugins:\n"
            "  foreman:\n"
            "    url: http://foreman.mylab.com/hosts/\n"
            "    api_url: https://foreman.mylab.com/api/v2\n"
            "  email:\n"
            "    smtp_host: mail.mylab.com\n"
        )
        (tmp_path / "oauth.yml").write_text("oauth_settings:\n  allowed_domains:\n    - 'mylab.com'\n")
        result = run_conf_check(str(tmp_path))
        assert not result.passed
        assert len(result.findings) == 1
        assert result.findings[0].key == "domain"

    def test_duplicate_keys_detected_in_integration(self, tmp_path):
        (tmp_path / "quads.yml").write_text("domain: mylab.com\ndomain: other.com\nquads_url: https://q.com\n")
        (tmp_path / "quadsweb.yml").write_text("key: value\n")
        (tmp_path / "selfservice.yml").write_text("key: value\n")
        (tmp_path / "plugins.yml").write_text(
            "plugins:\n  foreman:\n    url: http://f.com/hosts/\n    api_url: https://f.com/api/v2\n  email:\n    smtp_host: m.com\n"
        )
        (tmp_path / "oauth.yml").write_text("oauth_settings:\n  allowed_domains:\n    - 'mylab.com'\n")
        result = run_conf_check(str(tmp_path))
        dup_findings = [f for f in result.findings if f.check_type == "duplicate_key"]
        assert len(dup_findings) == 1
        assert dup_findings[0].key == "domain"


class TestConfCheckResult:
    def test_passed_when_no_findings(self):
        result = ConfCheckResult(findings=[], files_checked=5)
        assert result.passed

    def test_not_passed_with_findings(self):
        finding = CheckFinding("test.yml", "default_value", "error", "key", "msg")
        result = ConfCheckResult(findings=[finding], files_checked=5)
        assert not result.passed
