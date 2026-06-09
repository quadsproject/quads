#!/usr/bin/env python3

import base64
import logging
import os

from paramiko import SSHClient, AutoAddPolicy, SSHConfig, SSHException

logger = logging.getLogger(__name__)
logging.getLogger("paramiko").setLevel(logging.WARNING)


class SSHHelperException(Exception):
    pass


class SSHHelper(object):
    def __init__(self, _host, _user=None, _password=None):
        self.host = _host
        self.user = _user
        self.password = _password
        try:
            self.ssh = self.connect()
        except SSHHelperException as ex:
            raise SSHHelperException(f"{self.host}: {ex}")

    def __exit__(self, exc_type, exc_val, exc_tb):  # pragma: no cover
        self.disconnect()

    def connect(self):
        ssh = SSHClient()
        config = SSHConfig()
        config_path = os.path.expanduser("~/.ssh/config")
        if os.path.exists(config_path):
            with open(config_path) as _file:
                config.parse(_file)
        host_config = config.lookup(self.host)
        ssh.set_missing_host_key_policy(AutoAddPolicy())
        ssh.load_system_host_keys()

        try:
            ssh.connect(
                self.host,
                username=self.user,
                password=self.password,
                key_filename=host_config["identityfile"][0],
                allow_agent=False,
                timeout=30,
            )
        except (SSHException, TimeoutError) as ex:
            raise SSHHelperException(ex)

        transport = ssh.get_transport()
        channel = transport.open_session()
        channel.setblocking(1)
        return ssh

    def disconnect(self):
        self.ssh.close()

    def run_cmd(self, cmd):
        stdin, stdout, stderr = self.ssh.exec_command(cmd)
        errors = stderr.readlines()
        exit_code = stdout.channel.recv_exit_status()
        if errors or exit_code > 0:
            logger.error("There was something wrong with your SSH request")
            for line in errors:
                logger.debug(line)
            return False, errors
        else:
            logger.debug("Command executed successfully: %s" % cmd)
            return True, stdout.readlines()

    def copy_ssh_key(self, _ssh_key):

        with open(_ssh_key, "r") as _file:
            key = _file.readline().strip()

        command = 'echo "%s" >> ~/.ssh/authorized_keys' % key
        stdin, stdout, stderr = self.ssh.exec_command(command)

        if stderr.readlines():
            logger.error("There was something wrong with your SSH request")
            for line in stderr.readlines():
                logger.error(line)
        else:
            logger.info("Your key was copied successfully")

    def distribute_ssh_keys(self, key_lines):
        if not key_lines:
            return True
        keys_content = "\n".join(key_lines) + "\n"
        encoded = base64.b64encode(keys_content.encode()).decode()
        cmd = (
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
            f"echo '{encoded}' | base64 -d >> ~/.ssh/authorized_keys && "
            "sort -u -o ~/.ssh/authorized_keys ~/.ssh/authorized_keys && "
            "chmod 600 ~/.ssh/authorized_keys"
        )
        result, errors = self.run_cmd(cmd)
        if not result:
            logger.error("Failed to distribute SSH keys to %s" % self.host)
            for line in errors:
                logger.error(line)
        return result

    def remove_ssh_keys(self, key_lines):
        if not key_lines:
            return True
        for key_line in key_lines:
            key_line = key_line.strip()
            if not key_line:
                continue
            encoded = base64.b64encode(key_line.encode()).decode()
            cmd = (
                f"grep -Fxv \"$(echo '{encoded}' | base64 -d)\" "
                "~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp && "
                "mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys"
            )
            self.run_cmd(cmd)
        return True
