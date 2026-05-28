import logging

import pexpect

logger = logging.getLogger(__name__)


class AristaException(Exception):
    pass


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

    def _reset_interface(self):
        self.execute(f"default interface {self.switch_port}")
        self.execute(f"interface {self.switch_port}")

    def _set_speed(self):
        # QUADS stores interface speed in Gbps, EOS expects Mbps
        if self.port_speed and int(self.port_speed) > 0:
            self.execute(f"speed {int(self.port_speed) * 1000}")

    def _save(self):
        self.execute("write memory", "Copy completed")

    def set_port(self):
        """Move a server port to a new cloud VLAN (cloud move).

        dot1q-tunnel mirrors the Juniper driver's QinQ group: the cloud VLAN is
        pushed as an outer tag on ingress and popped on egress, so a host's own
        802.1Q tags survive instead of being dropped by an access port.
        """
        try:
            self.connect()
            self.execute("enable")
            self.execute("configure terminal")
            self._reset_interface()
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
            self.execute("enable")
            self.execute("configure terminal")
            self._reset_interface()
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
