import logging

import pexpect

from quads.config import Config
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException

logger = logging.getLogger(__name__)


class JuniperRoCEException(Exception):
    pass


BASE_CONFIG_COMMANDS = [
    "set class-of-service classifiers dscp STORAGE-CLASSIFIER forwarding-class nvme-tcp loss-priority low code-points 100000",
    "set class-of-service classifiers dscp STORAGE-CLASSIFIER forwarding-class roce-lossless loss-priority low code-points 011010",
    "set class-of-service classifiers dscp STORAGE-CLASSIFIER forwarding-class roce-lossless loss-priority low code-points 011000",
    "set class-of-service classifiers ieee-802.1 STORAGE-CLASSIFIER-L2 forwarding-class nvme-tcp loss-priority low code-points 100",
    "set class-of-service classifiers ieee-802.1 STORAGE-CLASSIFIER-L2 forwarding-class roce-lossless loss-priority low code-points 011",
    "set class-of-service drop-profiles roce-ecn-profile interpolate fill-level 55",
    "set class-of-service drop-profiles roce-ecn-profile interpolate fill-level 90",
    "set class-of-service drop-profiles roce-ecn-profile interpolate drop-probability 0",
    "set class-of-service drop-profiles roce-ecn-profile interpolate drop-probability 100",
    "set class-of-service forwarding-classes class best-effort queue-num 0",
    "set class-of-service forwarding-classes class roce-lossless queue-num 3",
    "set class-of-service forwarding-classes class roce-lossless no-loss",
    "set class-of-service forwarding-classes class nvme-tcp queue-num 4",
    "set class-of-service forwarding-classes class network-control queue-num 7",
    "set class-of-service congestion-notification-profile storage-cnp input ieee-802.1 code-point 011 pfc",
    "set class-of-service rewrite-rules ieee-802.1 STORAGE-REWRITE forwarding-class nvme-tcp loss-priority low code-point 100",
    "set class-of-service rewrite-rules ieee-802.1 STORAGE-REWRITE forwarding-class roce-lossless loss-priority low code-point 011",
    "set class-of-service scheduler-maps storage-fabric-map forwarding-class best-effort scheduler qinq-sched",
    "set class-of-service scheduler-maps storage-fabric-map forwarding-class network-control scheduler nc-sched",
    "set class-of-service scheduler-maps storage-fabric-map forwarding-class nvme-tcp scheduler nvme-sched",
    "set class-of-service scheduler-maps storage-fabric-map forwarding-class roce-lossless scheduler roce-sched",
    "set class-of-service schedulers nc-sched transmit-rate percent 5",
    "set class-of-service schedulers nc-sched priority strict-high",
    "set class-of-service schedulers nvme-sched transmit-rate percent 30",
    "set class-of-service schedulers nvme-sched priority low",
    "set class-of-service schedulers qinq-sched transmit-rate percent 15",
    "set class-of-service schedulers qinq-sched priority low",
    "set class-of-service schedulers roce-sched transmit-rate percent 50",
    "set class-of-service schedulers roce-sched priority low",
    "set class-of-service schedulers roce-sched drop-profile-map loss-priority low protocol any drop-profile roce-ecn-profile",
    "set class-of-service schedulers roce-sched explicit-congestion-notification",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-nvme from user-vlan-1p-priority 4",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-nvme then accept",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-nvme then forwarding-class nvme-tcp",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-nvme then loss-priority low",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-storage-prio from user-vlan-1p-priority 3",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-storage-prio then accept",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-storage-prio then forwarding-class roce-lossless",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-storage-prio then loss-priority low",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-roce-dscp from dscp 26",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-roce-dscp then accept",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-roce-dscp then forwarding-class roce-lossless",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term match-roce-dscp then loss-priority low",
    "set firewall family ethernet-switching filter RoCE-Ingress-Map term default then accept",
    "set class-of-service interfaces ae0 congestion-notification-profile storage-cnp",
    "set class-of-service interfaces ae0 scheduler-map storage-fabric-map",
    "set class-of-service interfaces ae0 unit * classifiers ieee-802.1 STORAGE-CLASSIFIER-L2",
    "set class-of-service interfaces ae0 unit * rewrite-rules ieee-802.1 STORAGE-REWRITE",
]

INTERFACE_CONFIG_TEMPLATE = [
    "set interfaces {switch_port} unit 0 family ethernet-switching filter input RoCE-Ingress-Map",
    "set class-of-service interfaces {switch_port} congestion-notification-profile storage-cnp",
    "set class-of-service interfaces {switch_port} scheduler-map storage-fabric-map",
]

BASE_CONFIG_DELETE_COMMANDS = [
    "delete class-of-service classifiers dscp STORAGE-CLASSIFIER",
    "delete class-of-service classifiers ieee-802.1 STORAGE-CLASSIFIER-L2",
    "delete class-of-service drop-profiles roce-ecn-profile",
    "delete class-of-service forwarding-classes class roce-lossless",
    "delete class-of-service forwarding-classes class nvme-tcp",
    "delete class-of-service forwarding-classes class best-effort",
    "delete class-of-service forwarding-classes class network-control",
    "delete class-of-service congestion-notification-profile storage-cnp",
    "delete class-of-service rewrite-rules ieee-802.1 STORAGE-REWRITE",
    "delete class-of-service scheduler-maps storage-fabric-map",
    "delete class-of-service schedulers nc-sched",
    "delete class-of-service schedulers nvme-sched",
    "delete class-of-service schedulers qinq-sched",
    "delete class-of-service schedulers roce-sched",
    "delete firewall family ethernet-switching filter RoCE-Ingress-Map",
    "delete class-of-service interfaces ae0 congestion-notification-profile",
    "delete class-of-service interfaces ae0 scheduler-map",
    "delete class-of-service interfaces ae0 unit * classifiers ieee-802.1 STORAGE-CLASSIFIER-L2",
    "delete class-of-service interfaces ae0 unit * rewrite-rules ieee-802.1 STORAGE-REWRITE",
]

INTERFACE_CONFIG_DELETE_TEMPLATE = [
    "delete interfaces {switch_port} unit 0 family ethernet-switching filter input RoCE-Ingress-Map",
    "delete class-of-service interfaces {switch_port} congestion-notification-profile",
    "delete class-of-service interfaces {switch_port} scheduler-map",
]


class JuniperRoCE:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.child = None

    def has_base_config(self):
        try:
            ssh = SSHHelper(self.ip_address, Config.plugins["juniper"]["username"])
            success, output = ssh.run_cmd(
                "show configuration class-of-service | display set | match STORAGE-CLASSIFIER"
            )
            ssh.disconnect()
            if success and output:
                return True
        except SSHHelperException:
            logger.warning(
                "Could not check existing config on %s, will attempt to apply",
                self.ip_address,
            )
        return False

    def connect(self):
        logger.debug("Connecting to switch: %s", self.ip_address)
        try:
            self.child = pexpect.spawn(
                f'ssh -o StrictHostKeyChecking=no {Config.plugins["juniper"]["username"]}@{self.ip_address}'
            )
            self.child.expect(">")
        except pexpect.exceptions.TIMEOUT:
            raise JuniperRoCEException("Timeout trying to connect via SSH")

    def execute(self, command, expect="#"):
        logger.debug(command)
        try:
            self.child.sendline(command)
            self.child.expect(expect, timeout=120)
        except pexpect.exceptions.TIMEOUT:
            raise JuniperRoCEException(f"Timeout trying to execute the command: {command}")

    def close(self):
        if self.child:
            self.child.close()

    def apply_base_config(self):
        try:
            self.execute("edit")
            self.execute("rollback")
            for cmd in BASE_CONFIG_COMMANDS:
                self.execute(cmd)
            self.execute("commit", "commit complete")
            self.execute("exit", ">")
        except JuniperRoCEException as ex:
            logger.error("Failed to apply base RoCE config: %s", ex)
            return False
        return True

    def apply_interface_config(self, switch_port):
        try:
            self.execute("edit")
            self.execute("rollback")
            for template in INTERFACE_CONFIG_TEMPLATE:
                self.execute(template.format(switch_port=switch_port))
            self.execute("commit", "commit complete")
            self.execute("exit", ">")
        except JuniperRoCEException as ex:
            logger.error("Failed to apply RoCE interface config for %s: %s", switch_port, ex)
            return False
        return True

    def remove_base_config(self):
        try:
            self.execute("edit")
            self.execute("rollback")
            for cmd in BASE_CONFIG_DELETE_COMMANDS:
                self.execute(cmd)
            self.execute("commit", "commit complete")
            self.execute("exit", ">")
        except JuniperRoCEException as ex:
            logger.error("Failed to remove base RoCE config: %s", ex)
            return False
        return True

    def remove_interface_config(self, switch_port):
        try:
            self.execute("edit")
            self.execute("rollback")
            for template in INTERFACE_CONFIG_DELETE_TEMPLATE:
                self.execute(template.format(switch_port=switch_port))
            self.execute("commit", "commit complete")
            self.execute("exit", ">")
        except JuniperRoCEException as ex:
            logger.error("Failed to remove RoCE interface config for %s: %s", switch_port, ex)
            return False
        return True
