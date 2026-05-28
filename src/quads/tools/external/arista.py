import logging
import pexpect

from quads.config import Config

logger = logging.getLogger(__name__)


class AristaException(Exception):
    pass


class Arista(object):
    def __init__(self, ip_address, switch_port, port_speed, old_vlan, new_vlan):
        self.ip_address = ip_address
        self.switch_port = switch_port
        self.port_speed = port_speed
        self.old_vlan = str(old_vlan)
        self.new_vlan = str(new_vlan)
        self.child = None

    def connect(self):
        logger.debug("Connecting to switch: %s" % self.ip_address)
        try:
            self.child = pexpect.spawn(
                f'ssh -o StrictHostKeyChecking=no {Config.plugins["arista"]["username"]}@{self.ip_address}'
            )
            self.child.expect(">")
        except pexpect.exceptions.TIMEOUT:
            raise AristaException("Timeout trying to connect via SSH")

    def close(self):
        self.child.close()

    def execute(self, command, expect="#"):
        logger.debug(command)
        try:
            self.child.sendline(command)
            self.child.expect(expect, timeout=120)
        except pexpect.exceptions.TIMEOUT:  # pragma: no cover
            raise AristaException(f"Timeout trying to execute the command: {command}")

    def set_port(self):
        try:
            self.connect()
            self.execute("enable")
            self.execute("configure terminal")

            if self.old_vlan and int(self.old_vlan) > 0:
                self.execute(f"no vlan {self.old_vlan}")

            self.execute(f"vlan {self.new_vlan}")
            self.execute(f"name QinQ_vl{self.new_vlan}")
            self.execute("exit")
            self.execute(f"interface {self.switch_port}")
            self.execute("switchport mode dot1q-tunnel")
            self.execute(f"switchport access vlan {self.new_vlan}")

            if int(self.port_speed) > 0:
                self.execute(f"speed forced {self.port_speed}gfull")

            self.execute("end")
            self.close()
        except AristaException as ex:
            logger.debug(ex)
            return False
        return True

    def convert_port_public(self):
        try:
            self.connect()
            self.execute("enable")
            self.execute("configure terminal")
            self.execute(f"interface {self.switch_port}")
            self.execute("switchport mode trunk")
            self.execute(f"switchport trunk native vlan {self.new_vlan}")
            self.execute(f"switchport trunk allowed vlan {self.new_vlan}")

            if int(self.port_speed) > 0:
                self.execute(f"speed forced {self.port_speed}gfull")

            if self.old_vlan and self.old_vlan != self.new_vlan:
                self.execute("exit")
                self.execute(f"no vlan {self.old_vlan}")

            self.execute("end")
            self.close()
        except AristaException as ex:
            logger.debug(ex)
            return False
        return True
