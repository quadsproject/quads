#!/usr/bin/env python3
import asyncio
import os
import re
import socket
from datetime import datetime
from jinja2 import Template
from paramiko import SSHException
from paramiko.ssh_exception import NoValidConnectionsError
from typing import List, Tuple, Dict, Any

from quads.plugins.interfaces.validator import ValidatorPlugin
from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.plugins.dispatchers.hardware import HardwareDispatcher
from quads.plugins.manager import PluginManager
from quads.tools.external.foreman import Foreman
from quads.tools.external.netcat import Netcat
from quads.tools.external.postman import Postman
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from quads.helpers.utils import is_supported
from src.quads.plugins.dispatchers import get_switch_dispatcher


class EnvironmentValidatorPlugin(ValidatorPlugin):
    """Environment validator plugin"""

    name = "environment"
    version = "1.0.0"
    description = "Standard environment validation for QUADS"
    author = "QUADS Team"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.quads = QuadsApi(Config)
        # Initialize plugin manager and hardware dispatcher for this instance
        self.plugin_manager = PluginManager()
        self.plugin_manager.initialize()
        self.hardware_dispatcher = HardwareDispatcher(self.plugin_manager)

    async def notify_failure(
        self,
        cloud: str,
        owner: str,
        ticket: str,
        report: str,
    ) -> None:
        """Send failure notification"""
        template_file = "validation_failed"
        with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
            template = Template(_file.read())
        parameters = {
            "cloud": cloud,
            "owner": owner,
            "ticket": ticket,
            "report": report,
        }
        content = template.render(**parameters)

        subject = "Validation check failed for {cloud} / {owner} / {ticket}".format(**parameters)
        _cc_users = Config["report_cc"].split(",")
        postman = Postman(subject, "dev-null", _cc_users, content)
        postman.send_email()

    async def notify_success(
        self,
        cloud: str,
        owner: str,
        ticket: str,
    ) -> None:
        """Send success notification"""
        template_file = "validation_succeeded"
        with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
            template = Template(_file.read())
        parameters = {
            "cloud": cloud,
            "owner": owner,
            "ticket": ticket,
        }
        content = template.render(**parameters)

        subject = "Validation check succeeded for {cloud} / {owner} / {ticket}".format(**parameters)
        _cc_users = Config["report_cc"].split(",")
        postman = Postman(subject, "dev-null", _cc_users, content)
        postman.send_email()

    async def env_allocation_time_exceeded(self, cloud: str) -> bool:
        """Check if the environment allocation time has exceeded the grace period"""
        now = datetime.now()
        data = {
            "cloud": cloud,
        }
        schedules = self.quads.get_current_schedules(data)
        if schedules:
            time_delta = now - schedules[0].start
            if time_delta.total_seconds() // 60 > Config["validation_grace_period"]:
                return True
            self.logger.warning(
                "You're still within the configurable validation grace period. Skipping validation for %s." % cloud
            )
        return False

    async def post_system_test(
        self,
        cloud: str,
        assignment,
        hosts: List,
        report: str = "",
    ) -> Tuple[bool, str]:
        """Run post-system validation tests"""
        self.logger.debug("Starting system test")
        password = f"{Config['infra_location']}@{assignment.ticket}"
        foreman = Foreman(
            Config["foreman_api_url"],
            cloud,
            password,
        )

        valid_creds = await foreman.verify_credentials()
        if not valid_creds:
            self.logger.error("Unable to query Foreman for cloud: %s" % cloud)
            self.logger.error("Verify Foreman password is correct: %s" % password)
            report += f"Unable to query Foreman for cloud: {cloud}\n"
            report += f"Verify Foreman password is correct: {password}\n"
            return False, report

        build_hosts = await foreman.get_build_hosts()

        pending = []
        for host in hosts:
            if host.name in build_hosts:
                pending.append(host)

        if pending:
            self.logger.info("The following hosts are marked for build and will now be rebooted:")
            report += "The following hosts are marked for build:\n"
            for host in pending:
                self.logger.info(host.name)
                try:
                    nc = Netcat(host.name)
                    healthy = await nc.health_check()
                except OSError:
                    healthy = False
                if not healthy:
                    self.logger.warning(
                        "Host %s didn't pass the health check. "
                        "Potential provisioning in process. SKIPPING." % host.name
                    )
                    continue

                # Setup hardware for this specific host
                try:
                    # Initialize dispatcher for this specific host
                    if await self.hardware_dispatcher.init_for_host(
                        host.name,
                        host.rack,
                        host.uloc,
                        host.blade,
                    ):
                        if is_supported(host.name):
                            await self.hardware_dispatcher.boot_to_type(
                                "foreman",
                                "/opt/quads/conf/idrac_interfaces.yml",
                            )
                        else:
                            await self.hardware_dispatcher.set_next_boot_pxe()
                        await self.hardware_dispatcher.reboot_server()
                    else:
                        self.logger.error(f"Could not initiate hardware for: {host.name}")
                except Exception as ಥ﹏ಥ:
                    self.logger.debug(ಥ﹏ಥ)
                    if self.hardware_dispatcher.has_plugins():
                        self.logger.warning(
                            f"There was something wrong trying to boot from Foreman interface for: {host.name}"
                        )
                        await self.hardware_dispatcher.reboot_server()
                    else:
                        self.logger.error(f"Could not initiate hardware for: {host.name}")

                report += f"{host.name}\n"
            return False, report

        tasks = [self.verify_hardware_creds(host, password) for host in hosts]
        results = await asyncio.gather(*tasks)

        return not any(results), report

    async def verify_hardware_creds(self, host, password):
        """Verify hardware credentials for a host"""
        self.logger.debug(f"Verifying hardware credentials for: {host.name}")
        try:
            # Create a new dispatcher instance for verification with custom credentials
            # We need a plugin instance we can modify, so we'll create one directly
            # Get the plugin class from the plugin manager
            plugin_manager_local = PluginManager()
            plugin_manager_local.initialize()
            hw_dispatcher = HardwareDispatcher(plugin_manager_local)

            # Initialize for the host
            if await hw_dispatcher.init_for_host(
                host.name,
                host.rack,
                host.uloc,
                host.blade,
            ):
                # Override with cloud username/password for verification
                hw_dispatcher._runtime_plugin.username = str(Config["ipmi_cloud_username"])
                hw_dispatcher._runtime_plugin.password = password
                # Re-initialize with new credentials
                await hw_dispatcher._runtime_plugin.init()
        except Exception:
            self.logger.info(f"Could not verify hardware credentials for: {host.name}")
            return True
        return False

    async def post_network_test(
        self,
        cloud: str,
        assignment,
        hosts: List,
        report: str = "",
    ) -> Tuple[bool, str]:
        """Run post-network validation tests"""
        self.logger.debug("Starting network test")
        test_host = hosts[0]
        hosts_down = []
        switch_config_missing = []
        for host in hosts:
            if not host.switch_config_applied:
                data = {"host": host.name, "cloud": host.cloud.name}
                current_schedule = self.quads.get_current_schedules(data)[0]
                previous_cloud = host.default_cloud.name
                data = {
                    "host": host.name,
                    "end": current_schedule.start.strftime("%Y-%m-%dT%H:%M"),
                }
                previous_schedule = self.quads.get_schedules(data=data)
                if previous_schedule:
                    previous_cloud = previous_schedule[0].assignment.cloud.name
                plugin_manager = PluginManager()
                switch_dispatcher = get_switch_dispatcher(plugin_manager)
                result = await switch_dispatcher.verify(host.name, previous_cloud, host.cloud.name)
                if result:
                    try:
                        self.quads.update_host(host.name, {"switch_config_applied": True})
                    except (APIServerException, APIBadRequest) as ex:
                        self.logger.debug(str(ex))
                        self.logger.error("Could not update host: %s." % host.name)
                        report = report + "Could not update host: %s.\n" % host.name
                        return False, report
                else:
                    switch_config_missing.append(host.name)
            try:
                nc = Netcat(host.name)
                healthy = await nc.health_check()
            except OSError:
                healthy = False
            if not healthy:
                hosts_down.append(host.name)
            if len(host.interfaces) > len(test_host.interfaces):
                test_host = host

        if hosts_down:
            self.logger.error("The following hosts appear to be down or with no ssh connection:")
            for i in hosts_down:
                self.logger.error(i)
            return False, report

        if switch_config_missing:
            self.logger.error("The following hosts are missing switch configuration:")
            for i in switch_config_missing:
                self.logger.error(i)
            return False, report

        failed_ssh = False
        try:
            ssh_helper = SSHHelper(test_host.name)
        except (
            SSHHelperException,
            SSHException,
            NoValidConnectionsError,
            socket.timeout,
        ) as ex:
            self.logger.debug(str(ex))
            self.logger.error("Could not establish connection with host: %s." % test_host.name)
            report = report + "Could not establish connection with host: %s.\n" % test_host.name
            failed_ssh = True

        if failed_ssh:
            return False, report

        host_list = " ".join([host.name for host in hosts])

        result, output = ssh_helper.run_cmd(f"fping -i 100 -t {Config.FPING_TIMEOUT} -B 1 -u {host_list}")
        if not result:
            return False, report

        for i, interface in enumerate(Config.INTERFACES.keys()):
            new_ips = []
            host_ips = [
                {"ip": socket.gethostbyname(host.name), "host": host}
                for host in hosts
                if interface in [_interface.name for _interface in host.interfaces]
            ]
            for host in host_ips:
                _host_obj = host["host"]
                _interfaces = Config.INTERFACES[interface]
                last_nic = i == len(_host_obj.interfaces) - 1
                if last_nic and assignment.vlan:
                    continue
                for value in _interfaces:
                    ip_apart = host["ip"].split(".")
                    octets = value.split(".")
                    ip_apart[0] = octets[0]
                    ip_apart[1] = octets[1]
                    new_ips.append(".".join(ip_apart))

            if new_ips:
                all_ips = " ".join(new_ips)
                result, output = ssh_helper.run_cmd(f"fping -i 100 -t {Config.FPING_TIMEOUT} -B 1 -u {all_ips}")
                if not result:
                    pattern = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
                    hosts_list = []
                    for error in output:
                        ip = pattern.search(error.split()[-1])[0]
                        if ip:
                            hosts_list.append(ip)
                    hosts_set = set(hosts_list)
                    self.logger.warning("The following IPs are not responsive:")
                    for host in hosts_set:
                        self.logger.warning(host)
                    return False, report

        ssh_helper.disconnect()

        return True, report

    async def validate(
        self,
        cloud: str,
        assignment,
        hosts: List,
        args,
        report: str = "",
    ) -> Tuple[bool, str]:
        """Validate an environment"""
        self.logger.info(f"Validating {cloud}")
        failed = False

        if await self.env_allocation_time_exceeded(cloud):
            if hosts:
                if not args.skip_system:
                    result_pst, report = await self.post_system_test(cloud, assignment, hosts, report)
                    if not result_pst:
                        failed = True

                if not args.skip_network:
                    result_pnt, report = await self.post_network_test(cloud, assignment, hosts, report)
                    if not failed and not result_pnt:
                        failed = True

            # TODO: gather ansible-cmdb facts

            # TODO: quads dell config report

            if not failed:
                if not assignment.notification.success:
                    await self.notify_success(cloud, assignment.owner, assignment.ticket)
                    try:
                        self.quads.update_notification(assignment.notification.id, {"success": True, "fail": False})
                    except (APIServerException, APIBadRequest) as ex:
                        self.logger.debug(str(ex))
                        self.logger.error("Could not update notification: %s." % assignment.notification.id)
                        report = report + "Could not update notification: %s.\n" % assignment.notification.id
                        failed = True

                for host in hosts:
                    try:
                        self.quads.update_host(host.name, {"validated": True})
                    except (APIServerException, APIBadRequest) as ex:
                        self.logger.debug(str(ex))
                        self.logger.error("Could not update host: %s." % host.name)
                        report = report + "Could not update host: %s.\n" % host.name
                        failed = True
                try:
                    self.quads.update_assignment(assignment.id, {"validated": True})
                except (APIServerException, APIBadRequest) as ex:
                    self.logger.debug(str(ex))
                    self.logger.error("Could not update assignment: %s." % assignment.id)
                    report = report + "Could not update assignment: %s.\n" % assignment.id
                    failed = True

        if failed and not assignment.notification.fail:
            await self.notify_failure(cloud, assignment.owner, assignment.ticket, report)
            try:
                self.quads.update_notification(assignment.notification.id, {"fail": True})
            except (APIServerException, APIBadRequest) as ex:
                self.logger.debug(str(ex))
                self.logger.error("Could not update notification: %s." % assignment.notification.id)
                report = report + "Could not update notification: %s.\n" % assignment.notification.id

        return not failed, report
