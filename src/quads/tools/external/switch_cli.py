"""Generic recipe-driven switch CLI runner.

Executes the command templates from ``conf/switch_commands.yml`` over
SSH (pexpect) for any switch vendor.  No vendor-specific Python code
lives here: the connection details, command sequences, save markers,
error markers and output parse patterns are all data.
"""

import logging
import re

import pexpect
from pexpect import exceptions as pexpect_exceptions

logger = logging.getLogger(__name__)


class SwitchCLIException(Exception):
    pass


class SwitchCLI(object):
    def __init__(self, vendor_cfg, params, dry_run=False):
        self.vendor_cfg = vendor_cfg or {}
        self.params = params or {}
        self.dry_run = dry_run
        self.child = None

    def _render(self, template):
        # Plain replacement, not str.format(): recipe parse patterns can
        # legitimately contain regex quantifiers like \d{1,3} which format
        # would treat as field specifications.
        missing = [name for name in re.findall(r"\{([A-Za-z_]\w*)\}", template) if name not in self.params]
        if missing:
            raise SwitchCLIException(f"Missing recipe parameter: {missing[0]}")
        for key, value in self.params.items():
            template = template.replace("{" + key + "}", str(value))
        return template

    def _connect(self):
        conn = self.vendor_cfg.get("connection", {})
        cmd = self._render(conn["ssh"])
        if self.dry_run:
            logger.info(f"SWITCH DRY-RUN: {cmd}")
            return
        # Wide PTY: narrow terminals wrap long show commands and the
        # continuation-line prompt would satisfy expect() before the
        # real output arrives.
        try:
            self.child = pexpect.spawn(cmd, dimensions=(24, 300))
            self.child.expect(conn["login_prompt"], timeout=self._timeout(conn))
        except (pexpect_exceptions.TIMEOUT, pexpect_exceptions.EOF,
                pexpect_exceptions.ExceptionPexpect) as ex:
            self._close()
            raise SwitchCLIException(f"Failed to connect to switch ({cmd}): {ex}")
        for init_command in conn.get("init_commands", []):
            self._command(init_command)

    def _timeout(self, conn):
        try:
            return int(conn.get("timeout", 120))
        except (TypeError, ValueError):
            return 120

    def _close(self):
        if self.child:
            try:
                self.child.close()
            except Exception:  # pragma: no cover
                pass
        self.child = None

    def _check_errors(self, output):
        for prefix in self.vendor_cfg.get("connection", {}).get("error_prefixes", []):
            for line in (output or "").splitlines():
                if line.strip().startswith(prefix):
                    raise SwitchCLIException(f"Switch rejected command: {line.strip()}")

    def _command(self, command, expect=None):
        if self.dry_run:
            logger.info(f"SWITCH DRY-RUN: {command}")
            return ""
        conn = self.vendor_cfg.get("connection", {})
        error_prefixes = conn.get("error_prefixes", [])
        self.child.sendline(command)
        # When a custom marker (e.g. save_wait) is expected, race it
        # against the prompt and the error prefixes: a rejected command
        # emits '% ...' and a prompt, never the marker, so a marker-only
        # expect would burn the whole timeout and hide the real error.
        patterns = None
        if expect is not None:
            patterns = [expect, conn["login_prompt"]] + error_prefixes
        try:
            if patterns:
                match_index = self.child.expect(patterns, timeout=self._timeout(conn))
            else:
                match_index = 0
                self.child.expect(conn["login_prompt"], timeout=self._timeout(conn))
        except (pexpect_exceptions.TIMEOUT, pexpect_exceptions.EOF,
                pexpect_exceptions.ExceptionPexpect) as ex:
            # A timeout may still have captured the rejection; surface
            # the actual switch error instead of a bare timeout.
            self._check_errors(self._decode(self.child.before))
            raise SwitchCLIException(f"Timeout executing command: {command} ({ex})")

        if patterns and match_index > 1:
            # An error prefix won the race; expect() consumed just the
            # prefix, so drain to the prompt and reconstruct the line.
            matched_prefix = self._decode(self.child.after)
            try:
                self.child.expect(conn["login_prompt"], timeout=5)
            except (pexpect_exceptions.TIMEOUT, pexpect_exceptions.EOF,
                    pexpect_exceptions.ExceptionPexpect):
                pass
            rejected = (matched_prefix + self._decode(self.child.before)).splitlines()
            for line in rejected:
                stripped = line.strip()
                if any(stripped.startswith(p) for p in error_prefixes):
                    raise SwitchCLIException(f"Switch rejected command: {stripped}")

        output = self._decode(self.child.before)
        self._check_errors(output)
        return output

    @staticmethod
    def _decode(output):
        if isinstance(output, bytes):
            return output.decode("utf-8", errors="replace")
        return output or ""

    def _run_get(self, operation):
        command = self._render(operation["command"])
        output = self._command(command)
        pattern = operation.get("parse", {}).get("pattern")
        if not pattern:
            return output
        pattern = self._render(pattern)
        try:
            match = re.search(pattern, output)
        except re.error as ex:
            raise SwitchCLIException(f"Invalid parse pattern {pattern!r}: {ex}")
        if not match:
            return None
        value = match.group(1)
        return int(value) if value.isdigit() else value

    def validate(self):
        """Raise SwitchCLIException when the recipe is structurally invalid."""
        conn = self.vendor_cfg.get("connection", {})
        for key in ("ssh", "login_prompt"):
            if not conn.get(key):
                raise SwitchCLIException(f"Recipe connection is missing required key '{key}'")
        operations = self.vendor_cfg.get("operations", {})
        if not operations:
            raise SwitchCLIException("Recipe defines no operations")
        for name, operation in operations.items():
            if not isinstance(operation, dict):
                raise SwitchCLIException(f"Operation '{name}' must be a mapping")
            is_get = "command" in operation
            is_set = "commands" in operation
            if is_get == is_set:
                raise SwitchCLIException(
                    f"Operation '{name}' must define exactly one of 'command' or 'commands'"
                )
            if is_set and not operation["commands"]:
                raise SwitchCLIException(f"Operation '{name}' has an empty command list")
            if not is_set:
                parse = operation.get("parse", {})
                pattern = parse.get("pattern") if isinstance(parse, dict) else None
                if pattern:
                    probe = re.sub(r"\{\w+\}", "x", pattern)
                    try:
                        re.compile(probe)
                    except re.error as ex:
                        raise SwitchCLIException(
                            f"Operation '{name}' has an invalid parse pattern: {ex}"
                        )

    def run(self, operation):
        """Run a recipe operation.

        Set-style operations (``commands``/``save``) return True on
        success.  Get-style operations (``command``/``parse``) return
        the parsed value, or None when the pattern does not match.
        """
        try:
            self._connect()
            if "command" in operation and "commands" not in operation:
                return self._run_get(operation)

            conn = self.vendor_cfg.get("connection", {})
            prompt = operation.get("config_prompt") or conn["login_prompt"]
            for entry in operation.get("commands", []):
                if isinstance(entry, dict):
                    if entry.get("if") and not self.params.get(entry["if"]):
                        continue
                    command = self._render(entry["cmd"])
                else:
                    command = self._render(entry)
                self._command(command, expect=prompt)

            saves = operation.get("save")
            if saves:
                if isinstance(saves, str):
                    saves = [saves]
                for index, save_cmd in enumerate(saves):
                    if index == len(saves) - 1:
                        expect = operation.get("save_wait") or prompt
                    else:
                        expect = prompt
                    self._command(self._render(save_cmd), expect=expect)
            return True
        finally:
            self._close()
