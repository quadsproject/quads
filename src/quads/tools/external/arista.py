import logging

import pexpect

from quads.config import Config

logger = logging.getLogger(__name__)


class AristaException(Exception):
    pass


class Arista:
    def __init__(self, ip_address, switch_port, port_speed, old_vlan, new_vlan):
        self.ip_address = ip_address
        self.switch_port = switch_port
        self.port_speed = port_speed
        self.old_vlan = str(old_vlan)
        self.new_vlan = str(new_vlan)
        self.child = None

    def connect(self):
        logger.debug(f"Connecting to switch: {self.ip_address}")
        try:
            self.child = pexpect.spawn(
                f'ssh -o StrictHostKeyChecking=no {Config.plugins["arista"]["username"]}@{self.ip_address}'
            )
            self.child.expect(r"[>#]")
        except pexpect.exceptions.TIMEOUT:
            raise AristaException("Timeout trying to connect via SSH")

    def close(self):
        self.child.close()

    def execute(self, command, expect=r"[>#]"):
        logger.debug(command)
        try:
            self.child.sendline(command)
            self.child.expect(expect, timeout=120)
            if self.child.before:
                for line in self.child.before.splitlines():
                    if line.strip().startswith("%"):
                        raise AristaException(f"Switch rejected: {line.strip()}")
        except pexpect.exceptions.TIMEOUT:  # pragma: no cover
            raise AristaException(f"Timeout trying to execute the command: {command}")

    def _reset_interface(self):
        self.execute(f"default interface {self.switch_port}")
        self.execute(f"interface {self.switch_port}")

    def _set_speed(self):
        if self.port_speed and int(self.port_speed) > 0:
            self.execute(f"speed {int(self.port_speed) * 1000}")

    def _save(self):
        self.execute("write memory", "Copy completed")

    def set_port(self):
        """Move a server port to a new private/access VLAN (cloud move)."""
        try:
            self.connect()
            self.execute("enable")
            self.execute("configure terminal")
            self._reset_interface()
            self.execute("switchport mode access")
            self.execute(f"switchport access vlan {self.new_vlan}")
            self._set_speed()
            self.execute("exit")
            self._save()
            self.close()
        except AristaException as ex:
            logger.debug(ex)
            return False
        return True

    def set_port_qinq(self):
        """Move a server port to a new QinQ outer VLAN (aggregation switch role).

        Equivalent to Juniper's 'apply-groups QinQ_vl<vlan>' configuration.
        """
        try:
            self.connect()
            self.execute("enable")
            self.execute("configure terminal")
            self.execute("l2-protocol tunnel dot1q")
            self._reset_interface()
            self.execute("switchport mode dot1q-tunnel")
            self.execute(f"switchport access vlan {self.new_vlan}")
            self._set_speed()
            self.execute("exit")
            self._save()
            self.close()
        except AristaException as ex:
            logger.debug(ex)
            return False
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
            self.close()
        except AristaException as ex:
            logger.debug(ex)
            return False
        return True
