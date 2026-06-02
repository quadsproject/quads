#!/usr/bin/env python3
import asyncio
import os
import re
import socket
from datetime import datetime
from jinja2 import Template
from paramiko import SSHException
from paramiko.ssh_exception import NoValidConnectionsError
from typing import List, Optional, Tuple

from quads.plugins.interfaces.validator import ValidatorPlugin
from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.tools.external.foreman import Foreman
from quads.tools.external.netcat import Netcat
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from quads.helpers.utils import is_supermicro
from quads.tools.external.ipmi import IPMI
from quads.plugins.dispatchers import get_hardware_dispatcher, get_switch_dispatcher, get_email_dispatcher
from quads.plugins.manager import PluginManager
from quads.server.models import Assignment


class EnvironmentValidatorPlugin(ValidatorPlugin):
    """
    Environment validator plugin implementing ValidatorPlugin interface.

    Manages environment validation and notification.
    """

    name = "environment"
    version = "1.0.0"
    description = "Standard environment validation for QUADS"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.quads = QuadsApi(Config)
        self.hardware_dispatcher = get_hardware_dispatcher(plugin_manager)
        self.switch_dispatcher = get_switch_dispatcher(plugin_manager)
        self.email_dispatcher = get_email_dispatcher(plugin_manager)
        return True

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
        _cc_users = Config.plugins["email"]["report_cc"].split(",")

        recipient = "%s@%s" % (owner, Config["domain"])
        await self.email_dispatcher.send_mail(
            subject=subject,
            content=content,
            recipients=[recipient],
            cc=_cc_users,
        )

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
        _cc_users = Config.plugins["email"]["report_cc"].split(",")
        recipient = "%s@%s" % (owner, Config["domain"])
        await self.email_dispatcher.send_mail(
            subject=subject,
            content=content,
            recipients=[recipient],
            cc=_cc_users,
        )

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
        ticket: str,
        hosts: List,
        report: str = "",
    ) -> Tuple[bool, str]:
        """Run post-system validation tests"""
        self.logger.debug("Starting system test")
        password = f"{Config['infra_location']}@{ticket}"
        foreman = Foreman(
            Config.plugins["foreman"]["api_url"],
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
                if is_supermicro(host.name):
                    config_ipmi = Config["plugins"]["badfish"]
                    ipmi = IPMI(
                        host.name, config_ipmi["ipmi_username"], config_ipmi["ipmi_password"], logger=self.logger
                    )
                    if not await ipmi.pxe_persistent():
                        self.logger.error(
                            f"There was something wrong setting PXE flag or resetting IPMI on {host.name}."
                        )
                else:
                    try:
                        # Initialize dispatcher for this specific host
                        if await self.hardware_dispatcher.init(
                            host.name,
                            host.rack,
                            host.uloc,
                            host.blade,
                        ):
                            if self.hardware_dispatcher.get_vendor() == "Dell":
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
            # Override with cloud username/password for verification
            self.hardware_dispatcher.username = str(Config["ipmi_cloud_username"])
            self.hardware_dispatcher.password = password
            # Re-initialize with new credentials
            await self.hardware_dispatcher.init(
                host.name,
                host.rack,
                host.uloc,
                host.blade,
            )
        except Exception:
            self.logger.info(f"Could not verify hardware credentials for: {host.name}")
            return True
        return False

    async def post_network_test(
        self,
        hosts: List,
        has_vlan: bool,
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
                result = await self.switch_dispatcher.verify(host.name, previous_cloud, host.cloud.name)
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
            return False, report

        host_list = " ".join([host.name for host in hosts])

        result, output = ssh_helper.run_cmd(f"fping -i 100 -t {Config.FPING_TIMEOUT} -B 1 -u {host_list}")
        if not result:
            report = report + output[0]
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
                if last_nic and has_vlan:
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

    def _get_progress_map(self, hosts):
        progress_map = {}
        for host in hosts:
            try:
                progress = self.quads.get_move_progress(host.name)
                if progress:
                    progress_map[host.name] = progress.get("id")
            except Exception:
                pass
        return progress_map

    def _update_progress(self, progress_id, status, message=""):
        if not progress_id:
            return
        try:
            data = {"status": status, "message": message}
            self.quads.update_move_progress(progress_id, data)
        except Exception:
            pass

    async def validate(
        self,
        cloud: str,
        assignment: Assignment,
        hosts: List,
        skip_system: bool,
        skip_network: bool,
        report: str = "",
    ) -> Tuple[bool, str]:
        """Validate an environment"""
        self.logger.info(f"Validating {cloud}")
        failed = False

        progress_map = self._get_progress_map(hosts)
        for host in hosts:
            self._update_progress(progress_map.get(host.name), "validation", "Running validation checks")

        if await self.env_allocation_time_exceeded(cloud):
            if hosts:
                if not skip_system:
                    result_pst, report = await self.post_system_test(cloud, assignment.ticket, hosts, report)
                    if not result_pst:
                        failed = True

                if not skip_network:
                    has_vlan = assignment.vlan is not None
                    result_pnt, report = await self.post_network_test(hosts, has_vlan, report)
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

                if not failed:
                    for host in hosts:
                        _pid = progress_map.get(host.name)
                        self._update_progress(_pid, "released", "Environment released to tenant")
                        self._update_progress(_pid, "completed")

        if failed and not assignment.notification.fail:
            await self.notify_failure(cloud, assignment.owner, assignment.ticket, report)
            try:
                self.quads.update_notification(assignment.notification.id, {"fail": True})
            except (APIServerException, APIBadRequest) as ex:
                self.logger.debug(str(ex))
                self.logger.error("Could not update notification: %s." % assignment.notification.id)
                report = report + "Could not update notification: %s.\n" % assignment.notification.id

        return not failed, report
