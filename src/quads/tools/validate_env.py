#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import re
import socket

from datetime import datetime
from jinja2 import Template
from paramiko import SSHException
from paramiko.ssh_exception import NoValidConnectionsError

from quads.config import Config, logging_manager
from quads.exceptions import CliException
from quads.helpers.utils import is_supported
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.tools.external.badfish import BadfishException, badfish_factory
from quads.tools.external.foreman import Foreman
from quads.tools.external.netcat import Netcat
from quads.tools.external.postman import Postman
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from quads.tools.external.switch import Switch


logger = logging_manager.get_tool_logger(__name__, level=logging.INFO)
quads = QuadsApi(Config)


class Validator(object):  # pragma: no cover
    def __init__(self, cloud, assignment, _args):
        logger.info(f"Initializing validator for cloud: {cloud}")
        self.cloud = cloud
        self.assignment = assignment
        self.report = ""
        self.args = _args

        # Get unvalidated hosts for this cloud
        self.hosts = quads.filter_hosts({"cloud": self.cloud, "validated": False})
        logger.debug(f"Found {len(self.hosts)} unvalidated hosts in {cloud}")

        # Filter to only hosts with current schedules
        self.hosts = [host for host in self.hosts if quads.get_current_schedules({"host": host.name})]
        logger.debug(f"Filtered to {len(self.hosts)} hosts with current schedules")

        # Handle skip hosts
        self.skip_hosts = self.args.skip_hosts[0] if self.args.skip_hosts else None
        if self.skip_hosts:
            logger.info(f"Skipping hosts: {', '.join(self.skip_hosts)}")
            self.hosts = [host for host in self.hosts if host.name not in self.skip_hosts]
            logger.info(f"Final host count after skipping: {len(self.hosts)}")

        if self.hosts:
            host_names = [host.name for host in self.hosts]
            logger.info(f"Hosts to validate: {', '.join(host_names)}")
        else:
            logger.info(f"No hosts to validate for cloud {cloud}")

    async def notify_failure(self):
        logger.info(f"Sending failure notification for cloud: {self.cloud}")
        logger.debug(
            f"Failure report content: {self.report[:200]}..."
            if len(self.report) > 200
            else f"Failure report: {self.report}"
        )

        template_file = "validation_failed"
        template_path = os.path.join(Config.TEMPLATES_PATH, template_file)
        logger.debug(f"Loading failure notification template: {template_path}")

        try:
            with open(template_path) as _file:
                template = Template(_file.read())

            parameters = {
                "cloud": self.cloud,
                "owner": self.assignment.owner,
                "ticket": self.assignment.ticket,
                "report": self.report,
            }
            content = template.render(**parameters)

            subject = "Validation check failed for {cloud} / {owner} / {ticket}".format(**parameters)
            _cc_users = Config["report_cc"].split(",")
            logger.info(f"Sending failure email to: {', '.join(_cc_users)} for {self.cloud}")

            postman = Postman(subject, "dev-null", _cc_users, content)
            postman.send_email()
            logger.info(f"Failure notification sent successfully for {self.cloud}")
        except Exception as e:
            logger.error(f"Failed to send failure notification for {self.cloud}: {e}")

    async def notify_success(self):
        logger.info(f"Sending success notification for cloud: {self.cloud}")

        template_file = "validation_succeeded"
        template_path = os.path.join(Config.TEMPLATES_PATH, template_file)
        logger.debug(f"Loading success notification template: {template_path}")

        try:
            with open(template_path) as _file:
                template = Template(_file.read())

            parameters = {
                "cloud": self.cloud,
                "owner": self.assignment.owner,
                "ticket": self.assignment.ticket,
            }
            content = template.render(**parameters)

            subject = "Validation check succeeded for {cloud} / {owner} / {ticket}".format(**parameters)
            _cc_users = Config["report_cc"].split(",")
            logger.info(f"Sending success email to: {', '.join(_cc_users)} for {self.cloud}")

            postman = Postman(subject, "dev-null", _cc_users, content)
            postman.send_email()
            logger.info(f"Success notification sent successfully for {self.cloud}")
        except Exception as e:
            logger.error(f"Failed to send success notification for {self.cloud}: {e}")

    async def env_allocation_time_exceeded(self):
        logger.debug(f"Checking if allocation time exceeded for {self.cloud}")
        now = datetime.now()
        data = {"cloud": self.cloud}

        schedules = quads.get_current_schedules(data)
        if schedules:
            start_time = schedules[0].start
            time_delta = now - start_time
            grace_period = Config["validation_grace_period"]
            elapsed_minutes = time_delta.total_seconds() // 60

            logger.info(
                f"Cloud {self.cloud} started at {start_time}, elapsed: {elapsed_minutes:.0f} minutes, grace period: {grace_period} minutes"
            )

            if elapsed_minutes > grace_period:
                logger.info(f"Grace period exceeded for {self.cloud}, proceeding with validation")
                return True
            else:
                remaining_minutes = grace_period - elapsed_minutes
                logger.warning(
                    f"Still within grace period for {self.cloud}. {remaining_minutes:.0f} minutes remaining. Skipping validation."
                )
        else:
            logger.warning(f"No current schedules found for {self.cloud}")

        return False

    async def post_system_test(self):
        logger.info(f"Starting system test for {self.cloud}")
        password = f"{Config['infra_location']}@{self.assignment.ticket}"
        logger.debug(
            f"Using Foreman password pattern for {self.cloud}: {Config['infra_location']}@{self.assignment.ticket}"
        )

        foreman = Foreman(
            Config["foreman_api_url"],
            self.cloud,
            password,
        )
        logger.debug(f"Initialized Foreman client for {self.cloud}")

        logger.info(f"Verifying Foreman credentials for {self.cloud}")
        valid_creds = await foreman.verify_credentials()
        if not valid_creds:
            logger.error(f"Foreman credential verification failed for {self.cloud}")
            logger.error(f"Failed password pattern: {Config['infra_location']}@{self.assignment.ticket}")
            self.report += f"Unable to query Foreman for cloud: {self.cloud}\n"
            self.report += f"Verify Foreman password is correct: {password}\n"
            return False

        logger.info(f"Foreman credentials verified successfully for {self.cloud}")

        logger.info(f"Fetching build hosts from Foreman for {self.cloud}")
        build_hosts = await foreman.get_build_hosts()
        logger.debug(f"Foreman reports {len(build_hosts)} hosts marked for build")

        pending = []
        for host in self.hosts:
            if host.name in build_hosts:
                pending.append(host)
                logger.debug(f"Host {host.name} is marked for build in Foreman")

        if pending:
            pending_names = [host.name for host in pending]
            logger.info(f"Found {len(pending)} hosts marked for build: {', '.join(pending_names)}")
            logger.info("These hosts will now be health-checked and rebooted")
            self.report += "The following hosts are marked for build:\n"

            for host in pending:
                logger.info(f"Processing build host: {host.name}")
                logger.debug(f"Performing health check on {host.name}")
                try:
                    nc = Netcat(host.name)
                    healthy = await nc.health_check()
                    if healthy:
                        logger.debug(f"Health check passed for {host.name}")
                    else:
                        logger.warning(f"Health check failed for {host.name}")
                except OSError as e:
                    logger.warning(f"Health check error for {host.name}: {e}")
                    healthy = False

                if not healthy:
                    logger.warning(
                        f"Host {host.name} failed health check - potential provisioning in progress. SKIPPING reboot."
                    )
                    continue

                logger.info(f"Health check passed for {host.name}, proceeding with reboot")
                logger.debug(
                    f"Initializing Badfish for {host.name} (rack: {host.rack}, uloc: {host.uloc}, blade: {host.blade})"
                )
                badfish = None
                try:
                    badfish = await badfish_factory(
                        "mgmt-" + host.name,
                        host.rack,
                        host.uloc,
                        host.blade,
                        str(Config["ipmi_username"]),
                        str(Config["ipmi_password"]),
                    )
                    logger.debug(f"Badfish initialized successfully for {host.name}")
                    if is_supported(host.name):
                        logger.info(f"Setting boot to Foreman interface for supported host: {host.name}")
                        await badfish.boot_to_type(
                            "foreman",
                            "/opt/quads/conf/idrac_interfaces.yml",
                        )
                        logger.debug(f"Boot type set to Foreman for {host.name}")
                    else:
                        logger.info(f"Setting PXE boot for unsupported host: {host.name}")
                        await badfish.set_next_boot_pxe()
                        logger.debug(f"PXE boot set for {host.name}")

                    logger.info(f"Rebooting server: {host.name}")
                    await badfish.reboot_server()
                    logger.info(f"Server reboot initiated for {host.name}")
                except BadfishException as ex:
                    logger.error(f"Badfish exception for {host.name}: {ex}")
                    if badfish:
                        logger.warning(f"Boot configuration failed for {host.name}, attempting simple reboot")
                        try:
                            await badfish.reboot_server()
                            logger.info(f"Fallback reboot completed for {host.name}")
                        except BadfishException as reboot_ex:
                            logger.error(f"Fallback reboot also failed for {host.name}: {reboot_ex}")
                    else:
                        logger.error(f"Could not initialize Badfish instance for {host.name}")

                self.report += f"{host.name}\n"
            return False

        logger.info(f"Verifying Badfish credentials for {len(self.hosts)} hosts in {self.cloud}")
        tasks = [self.verify_badfish_creds(host, password) for host in self.hosts]
        results = await asyncio.gather(*tasks)

        failed_hosts = [host.name for host, result in zip(self.hosts, results) if result]
        if failed_hosts:
            logger.warning(f"Badfish credential verification failed for: {', '.join(failed_hosts)}")
        else:
            logger.info(f"Badfish credentials verified for all hosts in {self.cloud}")

        system_test_passed = not any(results)
        logger.info(f"System test {'PASSED' if system_test_passed else 'FAILED'} for {self.cloud}")
        return system_test_passed

    @staticmethod
    async def verify_badfish_creds(host, password):
        logger.debug(f"Verifying Badfish credentials for: {host.name}")
        try:
            await badfish_factory(
                "mgmt-" + host.name,
                host.rack,
                host.uloc,
                host.blade,
                str(Config["ipmi_cloud_username"]),
                password,
            )
            logger.debug(f"Badfish credentials verified for: {host.name}")
            return False  # No error
        except BadfishException as ex:
            logger.warning(f"Badfish credential verification failed for {host.name}: {ex}")
            return True  # Error occurred

    async def post_network_test(self):
        logger.info(f"Starting network test for {self.cloud} with {len(self.hosts)} hosts")
        test_host = self.hosts[0]
        logger.info(f"Using {test_host.name} as primary test host")

        hosts_down = []
        switch_config_missing = []
        logger.info(f"Checking switch configuration and host connectivity for {len(self.hosts)} hosts")

        for host in self.hosts:
            logger.debug(f"Checking switch configuration for {host.name}")

            if not host.switch_config_applied:
                logger.info(f"Switch configuration not applied for {host.name}, verifying now")

                data = {"host": host.name, "cloud": host.cloud.name}
                current_schedule = quads.get_current_schedules(data)[0]
                previous_cloud = host.default_cloud.name

                # Get previous cloud assignment
                data = {
                    "host": host.name,
                    "end": current_schedule.start.strftime("%Y-%m-%dT%H:%M"),
                }
                previous_schedule = quads.get_schedules(data=data)
                if previous_schedule:
                    previous_cloud = previous_schedule[0].assignment.cloud.name

                logger.debug(f"Verifying switch config for {host.name}: {previous_cloud} -> {host.cloud.name}")
                switch = Switch()
                result = switch.verify(host.name, previous_cloud, host.cloud.name)

                if result:
                    logger.info(f"Switch configuration verified for {host.name}")
                    try:
                        quads.update_host(host.name, {"switch_config_applied": True})
                        logger.debug(f"Updated switch_config_applied flag for {host.name}")
                    except (APIServerException, APIBadRequest) as ex:
                        logger.error(f"Failed to update switch config flag for {host.name}: {ex}")
                        self.report += f"Could not update host: {host.name}\n"
                        return False
                else:
                    logger.warning(f"Switch configuration verification failed for {host.name}")
                    switch_config_missing.append(host.name)
            else:
                logger.debug(f"Switch configuration already applied for {host.name}")
            # Health check for connectivity
            logger.debug(f"Performing connectivity check for {host.name}")
            try:
                nc = Netcat(host.name)
                healthy = await nc.health_check()
                if healthy:
                    logger.debug(f"Connectivity check passed for {host.name}")
                else:
                    logger.warning(f"Connectivity check failed for {host.name}")
            except OSError as e:
                logger.warning(f"Connectivity check error for {host.name}: {e}")
                healthy = False

            if not healthy:
                hosts_down.append(host.name)

            # Update test host if this one has more interfaces
            if len(host.interfaces) > len(test_host.interfaces):
                logger.debug(
                    f"Updating test host to {host.name} (has {len(host.interfaces)} interfaces vs {len(test_host.interfaces)})"
                )
                test_host = host

        if hosts_down:
            logger.error(f"Network test failed: {len(hosts_down)} hosts are down or unreachable")
            for host in hosts_down:
                logger.error(f"Host down: {host}")
            self.report += f"Hosts down or unreachable: {', '.join(hosts_down)}\n"
            return False

        if switch_config_missing:
            logger.error(f"Network test failed: {len(switch_config_missing)} hosts missing switch configuration")
            for host in switch_config_missing:
                logger.error(f"Missing switch config: {host}")
            self.report += f"Hosts missing switch config: {', '.join(switch_config_missing)}\n"
            return False

        logger.info("All hosts passed connectivity and switch configuration checks")

        # Establish SSH connection to test host for network testing
        logger.info(f"Establishing SSH connection to test host: {test_host.name}")
        failed_ssh = False
        ssh_helper = None

        try:
            ssh_helper = SSHHelper(test_host.name)
            logger.debug(f"SSH connection established to {test_host.name}")
        except (
            SSHHelperException,
            SSHException,
            NoValidConnectionsError,
            socket.timeout,
        ) as ex:
            logger.error(f"SSH connection failed to {test_host.name}: {ex}")
            self.report += f"Could not establish SSH connection to {test_host.name}\n"
            failed_ssh = True

        if failed_ssh:
            logger.error(f"Network test aborted due to SSH connection failure to {test_host.name}")
            return False

        # Test basic connectivity between hosts
        host_list = " ".join([host.name for host in self.hosts])
        fping_cmd = f"fping -i 100 -t {Config.FPING_TIMEOUT} -B 1 -u {host_list}"

        logger.info(f"Testing basic connectivity between {len(self.hosts)} hosts using fping")
        logger.debug(f"Running fping command: {fping_cmd}")

        result, output = ssh_helper.run_cmd(fping_cmd)
        if not result:
            logger.error(f"Basic fping connectivity test failed for {self.cloud}")
            if output:
                logger.debug(f"Fping output: {output}")
            self.report += "Basic connectivity test failed between hosts\n"
            return False
        else:
            logger.info(f"Basic connectivity test passed for all hosts in {self.cloud}")

        # Test interface-specific connectivity
        logger.info(f"Testing interface-specific connectivity for {len(Config.INTERFACES)} interface types")

        for i, interface in enumerate(Config.INTERFACES.keys()):
            logger.debug(f"Testing interface: {interface}")
            new_ips = []

            # Get hosts that have this interface type
            host_ips = [
                {"ip": socket.gethostbyname(host.name), "host": host}
                for host in self.hosts
                if interface in [_interface.name for _interface in host.interfaces]
            ]

            if not host_ips:
                logger.debug(f"No hosts have interface {interface}, skipping")
                continue

            logger.debug(f"Found {len(host_ips)} hosts with interface {interface}")

            for host in host_ips:
                _host_obj = host["host"]
                _interfaces = Config.INTERFACES[interface]
                last_nic = i == len(_host_obj.interfaces) - 1

                if last_nic and self.assignment.vlan:
                    logger.debug(f"Skipping VLAN interface for {_host_obj.name} (last NIC with VLAN assignment)")
                    continue

                for value in _interfaces:
                    ip_apart = host["ip"].split(".")
                    octets = value.split(".")
                    ip_apart[0] = octets[0]
                    ip_apart[1] = octets[1]
                    new_ips.append(".".join(ip_apart))

            if new_ips:
                all_ips = " ".join(new_ips)
                interface_fping_cmd = f"fping -i 100 -t {Config.FPING_TIMEOUT} -B 1 -u {all_ips}"

                logger.info(f"Testing {interface} interface connectivity for {len(new_ips)} IPs")
                logger.debug(f"Interface fping command: {interface_fping_cmd}")

                result, output = ssh_helper.run_cmd(interface_fping_cmd)
                if not result:
                    logger.error(f"Interface connectivity test failed for {interface}")

                    # Parse failed IPs from output
                    pattern = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
                    failed_ips = []
                    for error in output:
                        match = pattern.search(error.split()[-1])
                        if match:
                            failed_ips.append(match.group(0))

                    failed_ips_set = set(failed_ips)
                    logger.error(f"The following {interface} IPs are not responsive: {', '.join(failed_ips_set)}")
                    self.report += f"Interface {interface} connectivity failed for IPs: {', '.join(failed_ips_set)}\n"
                    return False
                else:
                    logger.info(f"Interface {interface} connectivity test passed")
            else:
                logger.debug(f"No IPs to test for interface {interface}")

        # Clean up SSH connection
        if ssh_helper:
            ssh_helper.disconnect()
            logger.debug(f"SSH connection to {test_host.name} closed")

        logger.info(f"Network test PASSED for {self.cloud}")
        return True

    async def validate_env(self):
        logger.info(f"=== Starting environment validation for {self.cloud} ===")
        logger.info(f"Assignment owner: {self.assignment.owner}, ticket: {self.assignment.ticket}")

        failed = False
        assignment = quads.get_active_cloud_assignment(self.cloud)

        if await self.env_allocation_time_exceeded():
            if self.hosts:
                logger.info(f"Running validation tests for {len(self.hosts)} hosts in {self.cloud}")

                if not self.args.skip_system:
                    logger.info(f"Starting system test for {self.cloud}")
                    result_pst = await self.post_system_test()
                    if not result_pst:
                        logger.error(f"System test FAILED for {self.cloud}")
                        failed = True
                    else:
                        logger.info(f"System test PASSED for {self.cloud}")

                if not self.args.skip_network:
                    logger.info(f"Starting network test for {self.cloud}")
                    result_pnt = await self.post_network_test()
                    if not failed and not result_pnt:
                        logger.error(f"Network test FAILED for {self.cloud}")
                        failed = True
                    elif result_pnt:
                        logger.info(f"Network test PASSED for {self.cloud}")
            else:
                logger.warning(f"No hosts to validate for {self.cloud}")

            # TODO: gather ansible-cmdb facts

            # TODO: quads dell config report

            if not failed:
                logger.info(f"=== VALIDATION PASSED for {self.cloud} ===")

                # Send success notification if not already sent
                if not assignment.notification.success:
                    logger.info(f"Sending success notification for {self.cloud}")
                    await self.notify_success()
                    try:
                        quads.update_notification(assignment.notification.id, {"success": True, "fail": False})
                        logger.debug(f"Updated notification status to success for {self.cloud}")
                    except (APIServerException, APIBadRequest) as ex:
                        logger.error(f"Failed to update notification for {self.cloud}: {ex}")
                        self.report += f"Could not update notification: {assignment.notification.id}\n"
                        failed = True
                else:
                    logger.debug(f"Success notification already sent for {self.cloud}")

                # Mark all hosts as validated
                logger.info(f"Marking {len(self.hosts)} hosts as validated")
                for host in self.hosts:
                    try:
                        quads.update_host(host.name, {"validated": True})
                        logger.debug(f"Marked host {host.name} as validated")
                    except (APIServerException, APIBadRequest) as ex:
                        logger.error(f"Failed to update host {host.name}: {ex}")
                        self.report += f"Could not update host: {host.name}\n"
                        failed = True

                # Mark assignment as validated
                try:
                    quads.update_assignment(self.assignment.id, {"validated": True})
                    logger.info(f"Marked assignment {self.assignment.id} as validated for {self.cloud}")
                except (APIServerException, APIBadRequest) as ex:
                    logger.error(f"Failed to update assignment {self.assignment.id}: {ex}")
                    self.report += f"Could not update assignment: {self.assignment.id}\n"
                    failed = True

        # Handle validation failure
        if failed:
            logger.error(f"=== VALIDATION FAILED for {self.cloud} ===")
            if not assignment.notification.fail:
                logger.info(f"Sending failure notification for {self.cloud}")
                await self.notify_failure()
                try:
                    quads.update_notification(assignment.notification.id, {"fail": True})
                    logger.debug(f"Updated notification status to failed for {self.cloud}")
                except (APIServerException, APIBadRequest) as ex:
                    logger.error(f"Failed to update failure notification for {self.cloud}: {ex}")
                    self.report += f"Could not update notification: {assignment.notification.id}\n"
            else:
                logger.debug(f"Failure notification already sent for {self.cloud}")
        else:
            logger.info(f"=== VALIDATION COMPLETED SUCCESSFULLY for {self.cloud} ===")

        return


async def main(_args, _logger=None):  # pragma: no cover
    global logger
    if _logger:
        logger = _logger

    # start by setting any assignment provisioned flag to true if all hosts are validated
    _filter = {"active": True, "validated": False, "provisioned": False, "cloud__ne": "cloud01"}
    assignments = quads.filter_assignments(_filter)
    for _ass in assignments:
        provisioned = True
        _schedules = quads.get_current_schedules(data={"cloud": _ass.cloud.name})
        for _schedule in _schedules:
            if not _schedule.host.validated:
                provisioned = False
                break
        if provisioned:
            quads.update_assignment(
                _ass.id,
                {
                    "provisioned": True,
                },
            )

    _filter = {"active": True, "validated": False, "provisioned": True, "cloud__ne": "cloud01"}
    assignments = quads.filter_assignments(_filter)

    if type(_args) is dict:
        # Hack for tests to work
        _args = argparse.Namespace(**_args)

    if _args.cloud:
        try:
            quads.get_cloud(_args.cloud)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(ex)

    if _args.skip_hosts:
        hosts = []
        for hostname in _args.skip_hosts[0]:
            try:
                host = quads.get_host(hostname)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(ex)
            hosts.append(host)

    for ass in assignments:
        _schedules = quads.get_current_schedules(data={"cloud": ass.cloud.name})
        _schedule_count = len(_schedules)

        _assignment = quads.get_active_cloud_assignment(ass.cloud.name)
        if _schedule_count and _assignment.wipe:
            validator = Validator(ass.cloud.name, _assignment, _args)
            try:
                await validator.validate_env()
            except Exception as ex:
                logger.debug(ex)
                logger.info("Failed validation for %s" % ass.cloud.name)
        elif _schedule_count and not _assignment.wipe:
            logger.info(f"Auto-Validating {ass.cloud.name} as marked for no wipe")
            quads.update_assignment(ass.id, {"validated": True})
