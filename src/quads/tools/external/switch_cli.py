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
        try:
            return template.format(**self.params)
        except KeyError as ex:
            raise SwitchCLIException(f"Missing recipe parameter: {ex}")

    def _connect(self):
        conn = self.vendor_cfg.get("connection", {})
        cmd = self._render(conn["ssh"])
        if self.dry_run:
            logger.info(f"SWITCH DRY-RUN: {cmd}")
            return
        # Wide PTY: narrow terminals wrap long show commands and the
        # continuation-line prompt would satisfy expect() before the
        # real output arrives.
        self.child = pexpect.spawn(cmd, dimensions=(24, 300))
        try:
            self.child.expect(conn["login_prompt"], timeout=120)
        except pexpect_exceptions.TIMEOUT:
            self._close()
            raise SwitchCLIException(f"Timeout connecting to switch: {cmd}")
        for init_command in conn.get("init_commands", []):
            self._command(init_command)

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
        self.child.sendline(command)
        try:
            self.child.expect(expect or conn["login_prompt"], timeout=120)
        except pexpect_exceptions.TIMEOUT:  # pragma: no cover
            raise SwitchCLIException(f"Timeout executing command: {command}")
        output = self.child.before or b""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        self._check_errors(output)
        return output

    def _run_get(self, operation):
        command = self._render(operation["command"])
        output = self._command(command)
        pattern = operation.get("parse", {}).get("pattern")
        if not pattern:
            return output
        pattern = self._render(pattern)
        match = re.search(pattern, output)
        if not match:
            return None
        value = match.group(1)
        return int(value) if value.isdigit() else value

    def run(self, operation):
        """Run a recipe operation.

        Set-style operations (``commands``/``save``) return True on
        success.  Get-style operations (``command``/``parse``) return
        the parsed value, or None when the pattern does not match.
        """
        self._connect()
        try:
            if "command" in operation and "commands" not in operation:
                return self._run_get(operation)

            conn = self.vendor_cfg.get("connection", {})
            for entry in operation.get("commands", []):
                if isinstance(entry, dict):
                    if entry.get("if") and not self.params.get(entry["if"]):
                        continue
                    command = self._render(entry["cmd"])
                else:
                    command = self._render(entry)
                self._command(command)

            saves = operation.get("save")
            if saves:
                if isinstance(saves, str):
                    saves = [saves]
                for index, save_cmd in enumerate(saves):
                    expect = None
                    if index == len(saves) - 1:
                        expect = operation.get("save_wait") or conn["login_prompt"]
                    self._command(self._render(save_cmd), expect=expect)
            return True
        finally:
            self._close()
