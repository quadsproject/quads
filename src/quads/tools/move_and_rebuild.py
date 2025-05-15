#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime
from time import sleep

from quads.config import Config
from quads.helpers.utils import is_supported, get_vlan
from quads.quads_api import QuadsApi
from quads.tools.external.badfish import badfish_factory, BadfishException
from quads.tools.external.foreman import Foreman
from quads.tools.external.juniper import Juniper
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
quads = QuadsApi(Config)


def switch_config(host, old_cloud, new_cloud):  # pragma: no cover
    _host_obj = quads.get_host(host)
    _old_ass_cloud_obj = quads.get_active_cloud_assignment(old_cloud)
    _new_ass_cloud_obj = quads.get_active_cloud_assignment(new_cloud)
    if not _host_obj.interfaces:
        logger.error("Host has no interfaces defined.")
        return False
    logger.debug("Connecting to switch on: %s" % _host_obj.interfaces[0].switch_ip)
    switch_ip = None
    ssh_helper = None
    interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
    for i, interface in enumerate(interfaces):
        last_nic = i == len(_host_obj.interfaces) - 1
        if not switch_ip:
            switch_ip = interface.switch_ip
            try:
                ssh_helper = SSHHelper(switch_ip, Config["junos_username"])
            except SSHHelperException:
                logger.error(f"Failed to connect to switch: {switch_ip}")
                return False
        else:
            if switch_ip != interface.switch_ip:
                ssh_helper.disconnect()
                switch_ip = interface.switch_ip
                ssh_helper = SSHHelper(switch_ip, Config["junos_username"])
        result, old_vlan_out = ssh_helper.run_cmd("show configuration interfaces %s" % interface.switch_port)
        old_vlan = None
        if result and old_vlan_out:
            old_vlan = old_vlan_out[0].split(";")[0].split()[1][7:]
        if not old_vlan:
            if _new_ass_cloud_obj and not _new_ass_cloud_obj.vlan and not last_nic:
                logger.warning(
                    "Warning: Could not determine the previous VLAN for %s on %s, switch %s, switchport %s"
                    % (
                        host,
                        interface.name,
                        interface.switch_ip,
                        interface.switch_port,
                    )
                )
            old_vlan = get_vlan(_old_ass_cloud_obj, i, last_nic)

        new_vlan = get_vlan(_new_ass_cloud_obj, i, last_nic)

        if _new_ass_cloud_obj and _new_ass_cloud_obj.vlan and last_nic:
            if int(old_vlan) != int(_new_ass_cloud_obj.vlan.vlan_id):
                logger.info("Setting last interface to public vlan %s." % new_vlan)

                juniper = Juniper(
                    interface.switch_ip,
                    interface.switch_port,
                    interface.speed,
                    old_vlan,
                    _new_ass_cloud_obj.vlan.vlan_id,
                )
                success = juniper.convert_port_public()

                if success:
                    logger.info("Successfully updated switch settings.")
                else:
                    logger.error("There was something wrong updating switch for %s:%s" % (host, interface.name))
                    if ssh_helper:
                        ssh_helper.disconnect()
                    return False
        else:
            if int(old_vlan) != int(new_vlan):
                juniper = Juniper(interface.switch_ip, interface.switch_port, interface.speed, old_vlan, new_vlan)
                success = juniper.set_port()

                if success:
                    logger.info("Successfully updated switch settings.")
                else:
                    logger.error("There was something wrong updating switch for %s:%s" % (host, interface.name))
                    if ssh_helper:
                        ssh_helper.disconnect()
                    return False

    if ssh_helper:
        ssh_helper.disconnect()

    return True


async def execute_ipmi(host, arguments, semaphore):  # pragma: no cover
    ipmi_cmd = [
        "/usr/bin/ipmitool",
        "-I",
        "lanplus",
        "-H",
        "mgmt-%s" % host,
        "-U",
        Config["ipmi_username"],
        "-P",
        Config["ipmi_password"],
    ]
    logger.debug("Executing IPMI with argmuents: %s" % arguments)
    cmd = ipmi_cmd + arguments
    async with semaphore:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        logger.debug(f"{stdout.decode().strip()}")


async def ipmi_reset(host, semaphore):  # pragma: no cover
    ipmi_off = [
        "chassis",
        "power",
        "off",
    ]
    await execute_ipmi(host, ipmi_off, semaphore)
    sleep(Config["ipmi_reset_sleep"])
    ipmi_on = [
        "chassis",
        "power",
        "on",
    ]
    await execute_ipmi(host, ipmi_on, semaphore)


async def move_and_rebuild(host, new_cloud, semaphore, rebuild=False, loop=None):  # pragma: no cover
    build_start = datetime.now()
    logger.debug("Moving and rebuilding host: %s" % host)

    untouchable_hosts = Config["untouchable_hosts"]
    logger.debug("Untouchable hosts: %s" % untouchable_hosts)
    _host_obj = quads.get_host(host)

    if host in untouchable_hosts:
        logger.error("No way...")
        return False

    _target_cloud = quads.get_cloud(new_cloud)
    ticket = ""
    boot_order = Config.get("foreman_default_boot_order")
    _assignment = quads.get_active_cloud_assignment(_target_cloud.name)
    if _assignment:
        ticket = _assignment.ticket
        boot_order = _assignment.boot_order
    ipmi_new_pass = f"{Config['infra_location']}@{ticket}" if ticket else Config["ipmi_password"]

    ipmi_set_pass = [
        "user",
        "set",
        "password",
        str(Config["ipmi_cloud_username_id"]),
        ipmi_new_pass,
    ]

    new_semaphore = asyncio.Semaphore(20)
    await execute_ipmi(host, arguments=ipmi_set_pass, semaphore=new_semaphore)

    ipmi_set_operator = ["user", "priv", str(Config["ipmi_cloud_username_id"]), "0x4"]
    await execute_ipmi(host, arguments=ipmi_set_operator, semaphore=new_semaphore)

    badfish = None
    if rebuild and _target_cloud.name != _host_obj.default_cloud.name:
        if Config.pdu_management:
            # TODO: pdu management
            pass

        try:
            badfish = await badfish_factory(
                "mgmt-%s" % host,
                _host_obj.rack,
                _host_obj.uloc,
                _host_obj.blade,
                Config["ipmi_username"],
                Config["ipmi_password"],
                propagate=True,
            )
        except BadfishException:
            logger.error(f"Could not initialize Badfish. Verify ipmi credentials for mgmt-{host}.")
            return False

        if is_supported(host):
            try:
                interfaces_path = Config.get("badfish_interfaces_path")
                result = await badfish.change_boot(boot_order, interfaces_path)
                if result:
                    # wait 10 minutes for the boot order job to complete
                    await asyncio.sleep(600)
            except BadfishException:
                logger.error(f"Could not set boot order via Badfish for mgmt-{host}.")
                return False

        try:
            await badfish.set_power_state("on")
        except BadfishException:
            logger.error(f"Failed to power on {host}")
            return False
        foreman_results = []
        os_type = Config["foreman_default_os"]
        if _assignment:
            if _assignment.ostype:
                os_type = _assignment.ostype

        foreman = Foreman(
            Config["foreman_api_url"],
            Config["foreman_username"],
            Config["foreman_password"],
            semaphore=semaphore,
        )

        params = [
            {
                "name": "operatingsystems",
                "value": os_type,
                "identifier": "title",
            },
        ]

        available_os = await foreman.get_available_os()
        for os in available_os:
            if os["title"] == os_type:
                os_id = os["id"]
                break

        available_mediums = await foreman.get_mediums(os_id)
        params.append({"name": "media", "value": available_mediums[0]["name"]})

        available_ptables = await foreman.get_ptables(os_id)
        params.append({"name": "ptables", "value": available_ptables[0]["name"]})

        set_result = await foreman.set_host_parameter(host, "overcloud", "true")
        foreman_results.append(set_result)

        put_result = await foreman.put_parameter(host, "build", 1)
        foreman_results.append(put_result)

        put_param_result = await foreman.put_parameters_by_name(host, params)
        foreman_results.append(put_param_result)

        owner_id = await foreman.get_user_id(new_cloud)
        host_id = await foreman.get_host_id(host)
        put_result = await foreman.put_element("hosts", host_id, "owner_id", owner_id)
        foreman_results.append(put_result)

        for result in foreman_results:
            if isinstance(result, Exception) or not result:
                logger.error("There was something wrong setting Foreman host parameters.")
                return False

        try:
            await badfish.unmount_virtual_media()
        except BadfishException:
            logger.warning(f"Could not unmount virtual media for mgmt-{host}.")

        try:
            await badfish.detach_remote_image()
        except BadfishException:
            logger.warning(f"Could not detach remote image for mgmt-{host}.")

        if is_supported(host):
            if boot_order != Config["foreman_default_boot_order"]:
                try:
                    await badfish.boot_to_type(
                        "foreman",
                        "/opt/quads/conf/idrac_interfaces.yml",
                    )
                    await badfish.reboot_server(graceful=False)
                except BadfishException:
                    logger.error(f"Error setting PXE boot via Badfish on {host}.")
                    await badfish.reboot_server(graceful=False)
                    return False
        else:
            try:
                ipmi_pxe_persistent = [
                    "chassis",
                    "bootdev",
                    "pxe",
                    "options=persistent",
                ]
                await execute_ipmi(host, arguments=ipmi_pxe_persistent, semaphore=new_semaphore)
                await ipmi_reset(host, new_semaphore)
            except Exception as ex:
                logger.debug(ex)
                logger.error(f"There was something wrong setting PXE flag or resetting IPMI on {host}.")

    if _target_cloud.name == _host_obj.default_cloud.name:
        if not badfish:
            try:
                badfish = await badfish_factory(
                    "mgmt-%s" % host,
                    _host_obj.rack,
                    _host_obj.uloc,
                    _host_obj.blade,
                    Config["ipmi_username"],
                    Config["ipmi_password"],
                    propagate=True,
                )
            except BadfishException:
                logger.error(f"Could not initialize Badfish. Verify ipmi credentials for mgmt-{host}.")
                return False

        await badfish.set_power_state("off")

    data = {"host": _host_obj.name, "cloud": _target_cloud.name}
    schedule = quads.get_current_schedules(data)
    if schedule:
        data = {
            "build_start": build_start.strftime("%Y-%m-%dT%H:%M"),
            "build_end": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        }
        quads.update_schedule(schedule[0].id, data)
    logger.debug("Updating host: %s")
    data = {
        "cloud": _target_cloud.name,
        "build": True,
        "last_build": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "validated": False,
    }
    quads.update_host(_host_obj.name, data)
    return True
