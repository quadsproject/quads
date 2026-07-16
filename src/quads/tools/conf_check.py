import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


EXPECTED_FILES = [
    "quads.yml",
    "quadsweb.yml",
    "selfservice.yml",
    "plugins.yml",
    "oauth.yml",
]

DEFAULT_VALUE_CHECKS = [
    ("quads.yml", "domain", "example.com", "error"),
    ("quads.yml", "quads_url", "https://quads.scalelab.example.com", "error"),
    ("plugins.yml", "plugins.foreman.url", "http://foreman.example.com/hosts/", "error"),
    ("plugins.yml", "plugins.foreman.api_url", "https://foreman.example.com/api/v2", "error"),
    ("plugins.yml", "plugins.email.smtp_host", "mail.example.com", "error"),
]


@dataclass
class CheckFinding:
    file: str
    check_type: str
    severity: str
    key: str
    message: str


@dataclass
class ConfCheckResult:
    findings: list = field(default_factory=list)
    files_checked: int = 0

    @property
    def passed(self):
        return not self.findings


class _DuplicateKeyLoader(yaml.SafeLoader):
    pass


def _build_duplicate_key_loader():
    duplicates = []

    def _construct_mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        seen = {}
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                duplicates.append((key, key_node.start_mark.line + 1))
            seen[key] = True
        return yaml.SafeLoader.construct_mapping(loader, node, deep=deep)

    loader_cls = type("DupLoader", (_DuplicateKeyLoader,), {})
    loader_cls.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _construct_mapping,
    )
    return loader_cls, duplicates


def _resolve_dotted_path(data, dotted_key):
    parts = dotted_key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None, False
        current = current[part]
    return current, True


def check_yaml_syntax(filepath):
    try:
        with open(filepath, "r") as f:
            yaml.safe_load(f)
        return None
    except yaml.YAMLError as exc:
        msg = str(exc)
        if hasattr(exc, "problem_mark"):
            mark = exc.problem_mark
            msg = f"line {mark.line + 1}, column {mark.column + 1}: {exc.problem}"
        return CheckFinding(
            file=os.path.basename(filepath),
            check_type="syntax_error",
            severity="error",
            key="",
            message=msg,
        )


def find_duplicate_keys(filepath):
    loader_cls, duplicates = _build_duplicate_key_loader()
    try:
        with open(filepath, "r") as f:
            yaml.load(f, Loader=loader_cls)  # noqa: S506
    except yaml.YAMLError:
        return []

    findings = []
    basename = os.path.basename(filepath)
    for key, line in duplicates:
        findings.append(
            CheckFinding(
                file=basename,
                check_type="duplicate_key",
                severity="warning",
                key=str(key),
                message=f"Duplicate key '{key}' at line {line}",
            )
        )
    return findings


def check_default_values(conf_dir):
    findings = []
    loaded = {}

    for filename, dotted_key, default_val, severity in DEFAULT_VALUE_CHECKS:
        filepath = os.path.join(conf_dir, filename)
        if not os.path.isfile(filepath):
            continue

        if filename not in loaded:
            try:
                with open(filepath, "r") as f:
                    loaded[filename] = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                continue

        data = loaded[filename]
        value, found = _resolve_dotted_path(data, dotted_key)
        if not found:
            continue

        if value == default_val:
            findings.append(
                CheckFinding(
                    file=filename,
                    check_type="default_value",
                    severity=severity,
                    key=dotted_key,
                    message=f"'{dotted_key}' is set to default '{default_val}'",
                )
            )

    findings.extend(_check_oauth_defaults(conf_dir, loaded))
    return findings


def _check_oauth_defaults(conf_dir, loaded):
    oauth_path = os.path.join(conf_dir, "oauth.yml")
    if not os.path.isfile(oauth_path):
        return []

    if "oauth.yml" not in loaded:
        try:
            with open(oauth_path, "r") as f:
                loaded["oauth.yml"] = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            return []

    data = loaded["oauth.yml"]
    domains, found = _resolve_dotted_path(data, "oauth_settings.allowed_domains")
    if not found or not isinstance(domains, list):
        return []

    if "example.com" not in domains:
        return []

    ss_path = os.path.join(conf_dir, "selfservice.yml")
    require_auth = False
    if os.path.isfile(ss_path):
        if "selfservice.yml" not in loaded:
            try:
                with open(ss_path, "r") as f:
                    loaded["selfservice.yml"] = yaml.safe_load(f) or {}
            except yaml.YAMLError:
                pass
        require_auth = loaded.get("selfservice.yml", {}).get("require_auth_provider", False)

    if require_auth:
        severity = "error"
        message = (
            "'oauth_settings.allowed_domains' contains default 'example.com' " "and require_auth_provider is enabled"
        )
    else:
        severity = "warning"
        message = (
            "'oauth_settings.allowed_domains' contains default 'example.com'. "
            "Update this if you plan to use Google OAuth2"
        )

    return [
        CheckFinding(
            file="oauth.yml",
            check_type="default_value",
            severity=severity,
            key="oauth_settings.allowed_domains",
            message=message,
        )
    ]


def check_missing_files(conf_dir):
    findings = []
    for filename in EXPECTED_FILES:
        filepath = os.path.join(conf_dir, filename)
        if not os.path.isfile(filepath):
            findings.append(
                CheckFinding(
                    file=filename,
                    check_type="missing_file",
                    severity="error",
                    key="",
                    message=f"Configuration file '{filename}' not found",
                )
            )
    return findings


def run_conf_check(conf_dir):
    result = ConfCheckResult()

    result.findings.extend(check_missing_files(conf_dir))

    syntax_failed = set()
    for filename in EXPECTED_FILES:
        filepath = os.path.join(conf_dir, filename)
        if not os.path.isfile(filepath):
            continue
        result.files_checked += 1
        finding = check_yaml_syntax(filepath)
        if finding:
            result.findings.append(finding)
            syntax_failed.add(filename)

    for filename in EXPECTED_FILES:
        filepath = os.path.join(conf_dir, filename)
        if not os.path.isfile(filepath) or filename in syntax_failed:
            continue
        result.findings.extend(find_duplicate_keys(filepath))

    parseable_files = {
        f for f in EXPECTED_FILES if os.path.isfile(os.path.join(conf_dir, f)) and f not in syntax_failed
    }
    if parseable_files:
        result.findings.extend(check_default_values(conf_dir))

    return result
