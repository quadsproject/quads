import logging
import re

import pexpect

logger = logging.getLogger(__name__)


class AristaException(Exception):
    pass


def expected_speed_statement(port_speed):
    """Return the EOS speed statement for a quads speed in Gbps.

    Returns None when the speed is unset (0/None), so callers can skip the
    speed configuration entirely.
    """
    if not port_speed or int(port_speed) <= 0:
        return None
    speed = int(port_speed) * 1000
    token = {
        1000: "forced 1000full",
        10000: "forced 10gfull",
        25000: "forced 25gfull",
        40000: "forced 40gfull",
        100000: "auto 100g-2",
    }.get(speed, f"forced {speed // 1000}gfull")
    return f"speed {token}"


_SPEED_FORCED_RE = re.compile(r"^speed\s+forced\s+(\d+)(g)?\w*$", re.I)
_SPEED_AUTO_RE = re.compile(r"^speed\s+auto(?:\s+(\S+))?$", re.I)


def _parse_speed_statement(statement):
    """Normalize an EOS speed statement to (mode, Mbps or auto qualifier).

    EOS may render the stored token differently from the command form, e.g.
    'speed forced 10000full' for 'speed forced 10gfull'. The Mbps value is the
    comparable part; None means the line is not a speed statement.
    """
    match = _SPEED_FORCED_RE.match((statement or "").strip())
    if match:
        value = int(match.group(1))
        return ("forced", value * 1000 if match.group(2) else value)
    match = _SPEED_AUTO_RE.match((statement or "").strip())
    if match:
        return ("auto", match.group(1) or "")
    return None


def speed_statement_matches(expected, lines):
    """Return True when running-config lines contain the expected speed.

    Compares the parsed mode/value instead of the raw line so a canonicalized
    EOS token does not report false speed drift during verify().
    """
    want = _parse_speed_statement(expected)
    if not want:
        return False
    for line in lines or []:
        got = _parse_speed_statement(line)
        if not got or got[0] != want[0]:
            continue
        if want[0] == "forced":
            if got[1] == want[1]:
                return True
        elif got[1] in ("", want[1]):
            return True
    return False


class Arista:
    def __init__(self, ip_address, switch_port, port_speed, old_vlan, new_vlan, username):
        self.ip_address = ip_address
        self.switch_port = switch_port
        self.port_speed = port_speed
        self.old_vlan = str(old_vlan)
        self.new_vlan = str(new_vlan)
        self.username = username
        self.child = None

    def connect(self):
        logger.debug(f"Connecting to switch: {self.ip_address}")
        if not self.username:
            raise AristaException("No username configured for the arista plugin (plugins.yml: arista.username)")
        try:
            # encoding is required: output is inspected as text in execute()
            self.child = pexpect.spawn(
                f"ssh -o StrictHostKeyChecking=no {self.username}@{self.ip_address}",
                encoding="utf-8",
            )
            self.child.expect(r"[>#]")
            # EOS paginates long output; disable it for the whole session
            # (tested on the POC fabric).
            self.execute("terminal length 0")
        except pexpect.exceptions.TIMEOUT:
            raise AristaException("Timeout trying to connect via SSH")

    def close(self):
        if self.child:
            self.child.close()

    def execute(self, command, expect=r"[>#]"):
        logger.debug(command)
        try:
            self.child.sendline(command)
            self.child.expect(expect, timeout=120)
            for line in self.child.before.splitlines():
                if line.strip().startswith("%"):
                    raise AristaException(f"Switch rejected: {line.strip()}")
        except pexpect.exceptions.TIMEOUT:  # pragma: no cover
            raise AristaException(f"Timeout trying to execute the command: {command}")

    def _enter_interface(self):
        # No 'default interface': it wipes every setting on the port.
        # Instead explicitly 'no' the opposite mode's settings, then apply
        # ours (tested on the POC fabric; EOS 'no' forms are idempotent).
        self.execute(f"interface {self.switch_port}")

    def _set_speed(self):
        # interface.speed is stored in Gbps (--interface-speed docs). Keep the
        # command sequence identical to the generic recipe: for 100G, RS-FEC
        # precedes the speed statement. EOS rejects 'speed forced 100gfull',
        # so 100G always uses 'speed auto 100g-2'.
        statement = expected_speed_statement(self.port_speed)
        if not statement:
            return
        if int(self.port_speed) == 100:
            self.execute("error-correction encoding reed-solomon")
        self.execute(statement)

    def _save(self):
        # Tested sequence: write memory followed by copy running-config
        # startup-config, matching the generic recipe's save steps.
        self.execute("write memory", "Copy completed")
        self.execute("copy running-config startup-config", "Copy completed")

    def set_port(self):
        """Move a server port to a new cloud VLAN (cloud move).

        dot1q-tunnel mirrors the Juniper driver's QinQ group: the cloud VLAN is
        pushed as an outer tag on ingress and popped on egress, so a host's own
        802.1Q tags survive instead of being dropped by an access port.
        """
        try:
            self.connect()
            self.execute("configure terminal")
            self._enter_interface()
            self.execute("no switchport trunk native vlan")
            self.execute("no switchport trunk allowed vlan")
            self.execute("switchport mode dot1q-tunnel")
            self.execute(f"switchport access vlan {self.new_vlan}")
            self._set_speed()
            self.execute("exit")
            self._save()
        except AristaException as ex:
            logger.debug(ex)
            return False
        finally:
            self.close()
        return True

    def convert_port_public(self):
        """Convert a server port to a public trunk VLAN."""
        try:
            self.connect()
            self.execute("configure terminal")
            self._enter_interface()
            self.execute("no switchport access vlan")
            self.execute("switchport mode trunk")
            self.execute(f"switchport trunk native vlan {self.new_vlan}")
            self.execute(f"switchport trunk allowed vlan {self.new_vlan}")
            self._set_speed()
            self.execute("exit")
            self._save()
        except AristaException as ex:
            logger.debug(ex)
            return False
        finally:
            self.close()
        return True
