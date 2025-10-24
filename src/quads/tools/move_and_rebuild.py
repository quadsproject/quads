#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from quads.config import Config
from quads.helpers.utils import is_supported
from quads.quads_api import QuadsApi
from quads.plugins.dispatchers.hardware import HardwareDispatcher
from quads.plugins.manager import PluginManager
from quads.plugins_builtin.hardware.badfish import BadfishHardwarePlugin
from quads.tools.external.foreman import Foreman
from quads.tools.external.ipmi import IPMI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
quads = QuadsApi(Config)

DEFAULT_HOST_UPDATE_DATA = {
    "build": False,
    "validated": False,
    "switch_config_applied": False,
}

# Initialize plugin manager and hardware dispatcher
plugin_manager = PluginManager()
hardware_dispatcher = HardwareDispatcher(plugin_manager)


async def setup_hardware_for_host(host: str, rack: str, uloc: str, blade: str) -> bool:
    """
    Setup hardware management for a specific host.
    This initializes the hardware plugin with host-specific parameters.
    """
    try:
        # For now, we need to create a host-specific plugin instance
        # since hardware operations are per-host
        hardware_plugin = BadfishHardwarePlugin(host, rack, uloc, blade)
        await hardware_plugin.init()
        # Store in dispatcher for this host context
        hardware_dispatcher._default_plugin = hardware_plugin
        return True
    except Exception as e:
        logger.error(f"Could not initialize hardware for {host}: {e}")
        return False


async def prepare_foreman_rebuild(host: str, new_cloud: str, os_type: str, semaphore: asyncio.Semaphore) -> bool:
    """Prepare host for rebuild in Foreman."""
    foreman = Foreman(
        Config["foreman_api_url"],
        Config["foreman_username"],
        Config["foreman_password"],
        semaphore=semaphore,
    )

    foreman_results = []

    try:
        available_os = await foreman.get_available_os()
        os_id = next((os["id"] for os in available_os if os["title"] == os_type), None)

        if not os_id:
            logger.error(f"OS type {os_type} not found in Foreman")
            return False

        params = [{"name": "operatingsystems", "value": os_type, "identifier": "title"}]

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

        return True
    except Exception as ex:
        logger.error(f"Error setting up Foreman for {host}: {ex}")
        return False


def _update_host_on_failure(host_obj, data: Dict[str, Any] = None) -> None:
    """Helper function to update host with failure data."""
    update_data = data or DEFAULT_HOST_UPDATE_DATA.copy()
    quads.update_host(host_obj.name, update_data)


async def move_and_rebuild(
    host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
) -> bool:  # pragma: no cover
    build_start = datetime.now()
    logger.debug(f"Moving and rebuilding host: {host}")

    untouchable_hosts = Config["untouchable_hosts"]
    logger.debug(f"Untouchable hosts: {untouchable_hosts}")

    host_obj = quads.get_host(host)
    if host in untouchable_hosts:
        logger.error(f"Host {host} is in untouchable hosts list")
        return False

    target_cloud = quads.get_cloud(new_cloud)
    ticket = ""
    boot_order = Config.get("foreman_default_boot_order")
    _assignment = quads.get_active_cloud_assignment(target_cloud.name)
    if _assignment:
        ticket = _assignment.ticket
        if _assignment.boot_order:
            boot_order = _assignment.boot_order
    ipmi_new_pass = f"{Config['infra_location']}@{ticket}" if ticket else Config["ipmi_password"]

    ipmi = IPMI(host, Config["ipmi_username"], Config["ipmi_password"], logger=logger)
    await ipmi.configure_user(Config["ipmi_cloud_username_id"], ipmi_new_pass)

    hardware_initialized = False
    if rebuild and target_cloud.name != host_obj.default_cloud.name:
        if Config.pdu_management:
            # TODO: pdu management
            pass

        # Initialize hardware via dispatcher
        if not await setup_hardware_for_host(host, host_obj.rack, host_obj.uloc, host_obj.blade):
            logger.debug(f"Updating host: {host}")
            _update_host_on_failure(host_obj)
            return False
        hardware_initialized = True

        if is_supported(host) and boot_order != Config.get("foreman_default_boot_order"):
            if not await hardware_dispatcher.change_boot(boot_order, Config.get("badfish_interfaces_path")):
                logger.error(f"Could not set boot order for {host}.")
                _update_host_on_failure(host_obj)
                return False
            # wait 10 minutes for the boot order job to complete
            await asyncio.sleep(600)

        if not await hardware_dispatcher.set_power_state("on"):
            logger.error(f"Failed to power on {host}")
            _update_host_on_failure(host_obj)
            return False

        os_type = Config["foreman_default_os"]
        if _assignment and _assignment.ostype:
            os_type = _assignment.ostype

        # Prepare Foreman for rebuild
        if not await prepare_foreman_rebuild(host, new_cloud, os_type, semaphore):
            _update_host_on_failure(host_obj)
            return False

        if not await hardware_dispatcher.unmount_virtual_media():
            logger.warning(f"Could not unmount virtual media for {host}.")

        if not await hardware_dispatcher.detach_remote_image():
            logger.warning(f"Could not detach remote image for {host}.")

        if is_supported(host):
            if boot_order != Config.get("foreman_default_boot_order"):
                if not await hardware_dispatcher.boot_to_type(
                    Config.get("foreman_default_boot_order"),
                    Config.get("badfish_interfaces_path"),
                ):
                    logger.error(f"Error setting PXE boot on {host}.")
                    _update_host_on_failure(host_obj)
                    return False
            if not await hardware_dispatcher.reboot_server(graceful=False):
                logger.error(f"Error rebooting server: {host}")
                _update_host_on_failure(host_obj)
                return False
        else:
            try:
                await ipmi.pxe_persistent()
            except Exception as ex:
                logger.debug(f"IPMI PXE error for {host}: {ex}")
                logger.error(f"There was something wrong setting PXE flag or resetting IPMI on {host}.")

    if target_cloud.name == host_obj.default_cloud.name:
        if not hardware_initialized:
            if not await setup_hardware_for_host(host, host_obj.rack, host_obj.uloc, host_obj.blade):
                _update_host_on_failure(host_obj)
                return False

        if not await hardware_dispatcher.set_power_state("off"):
            logger.error(f"Failed to power off {host}")
            _update_host_on_failure(host_obj)
            return False

    data = {"host": host_obj.name, "cloud": target_cloud.name}
    schedule = quads.get_current_schedules(data)
    if schedule:
        schedule_update_data = {
            "build_start": build_start.strftime("%Y-%m-%dT%H:%M"),
            "build_end": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        }
        quads.update_schedule(schedule[0].id, schedule_update_data)

    logger.debug(f"Updating host: {host}")
    success_data = {
        "cloud": target_cloud.name,
        "build": True,
        "last_build": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "validated": False,
    }
    quads.update_host(host_obj.name, success_data)
    return True
