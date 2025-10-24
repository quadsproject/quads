"""
Standard Release Plugin - Default implementation for host release/rebuild
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from quads.config import Config
from quads.helpers.utils import is_supported
from quads.plugins.interfaces.release import ReleasePlugin
from quads.plugins.dispatchers.hardware import HardwareDispatcher
from quads.plugins.manager import PluginManager
from quads.plugins_builtin.hardware.badfish import BadfishHardwarePlugin
from quads.quads_api import QuadsApi
from quads.tools.external.foreman import Foreman
from quads.tools.external.ipmi import IPMI

logger = logging.getLogger(__name__)


class StandardReleasePlugin(ReleasePlugin):
    """
    Standard release plugin for moving and rebuilding hosts.

    Handles:
    - Hardware preparation (boot order, power management)
    - Provisioner setup (Foreman)
    - Host rebuild orchestration
    - IPMI fallback for unsupported hosts
    """

    def __init__(self):
        self.quads = QuadsApi(Config)
        self.plugin_manager = PluginManager()
        self.hardware_dispatcher = HardwareDispatcher(self.plugin_manager)

    async def move_and_rebuild(
        self, host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
    ) -> bool:
        """Move a host to a new cloud and optionally rebuild it"""
        build_start = datetime.now()
        logger.debug(f"Moving and rebuilding host: {host}")

        # Check if host is untouchable
        untouchable_hosts = Config["untouchable_hosts"]
        if host in untouchable_hosts:
            logger.error(f"Host {host} is in untouchable hosts list")
            return False

        host_obj = self.quads.get_host(host)
        target_cloud = self.quads.get_cloud(new_cloud)

        # Get boot order and ticket info
        boot_order = Config.get("foreman_default_boot_order")
        ticket = ""
        _assignment = self.quads.get_active_cloud_assignment(target_cloud.name)
        if _assignment:
            ticket = _assignment.ticket
            if _assignment.boot_order:
                boot_order = _assignment.boot_order

        # Configure IPMI
        ipmi_new_pass = f"{Config['infra_location']}@{ticket}" if ticket else Config["ipmi_password"]
        ipmi = IPMI(host, Config["ipmi_username"], Config["ipmi_password"], logger=logger)
        await ipmi.configure_user(Config["ipmi_cloud_username_id"], ipmi_new_pass)

        hardware_initialized = False
        if rebuild and target_cloud.name != host_obj.default_cloud.name:
            # Handle PDU management if configured
            if Config.pdu_management:
                # TODO: pdu management
                pass

            # Prepare hardware
            if not await self.prepare_host_hardware(
                host, host_obj.rack, host_obj.uloc, host_obj.blade, boot_order, Config.get("badfish_interfaces_path")
            ):
                self._update_host_on_failure(host_obj)
                return False
            hardware_initialized = True

            # Power on
            if not await self.power_on_host(host, host_obj.rack, host_obj.uloc, host_obj.blade):
                logger.error(f"Failed to power on {host}")
                self._update_host_on_failure(host_obj)
                return False

            # Prepare provisioning
            os_type = Config["foreman_default_os"]
            if _assignment and _assignment.ostype:
                os_type = _assignment.ostype

            if not await self.prepare_host_provisioning(host, new_cloud, os_type, semaphore):
                self._update_host_on_failure(host_obj)
                return False

            # Cleanup virtual media
            await self.cleanup_virtual_media(host, host_obj.rack, host_obj.uloc, host_obj.blade)

            # Reboot for rebuild (supported hosts only)
            if is_supported(host):
                if not await self._reboot_for_rebuild(
                    host, host_obj, boot_order, Config.get("badfish_interfaces_path")
                ):
                    self._update_host_on_failure(host_obj)
                    return False
            else:
                # Fallback to IPMI for unsupported hosts
                try:
                    await ipmi.pxe_persistent()
                except Exception as ex:
                    logger.debug(f"IPMI PXE error for {host}: {ex}")
                    logger.error(f"There was something wrong setting PXE flag or resetting IPMI on {host}.")

        # Power off if moving back to default cloud
        if target_cloud.name == host_obj.default_cloud.name:
            if not hardware_initialized:
                await self._setup_hardware_for_host(host, host_obj.rack, host_obj.uloc, host_obj.blade)

            if not await self.power_off_host(host, host_obj.rack, host_obj.uloc, host_obj.blade):
                logger.error(f"Failed to power off {host}")
                self._update_host_on_failure(host_obj)
                return False

        # Update schedule
        data = {"host": host_obj.name, "cloud": target_cloud.name}
        schedule = self.quads.get_current_schedules(data)
        if schedule:
            schedule_update_data = {
                "build_start": build_start.strftime("%Y-%m-%dT%H:%M"),
                "build_end": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            }
            self.quads.update_schedule(schedule[0].id, schedule_update_data)

        # Update host
        success_data = {
            "cloud": target_cloud.name,
            "build": True,
            "last_build": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "validated": False,
        }
        self.quads.update_host(host_obj.name, success_data)
        return True

    async def prepare_host_hardware(
        self, host: str, rack: str, uloc: str, blade: str, boot_order: str, interfaces_path: str
    ) -> bool:
        """Prepare host hardware for rebuild"""
        try:
            # Initialize hardware plugin
            hardware_plugin = BadfishHardwarePlugin(host, rack, uloc, blade)
            await hardware_plugin.init()
            self.hardware_dispatcher._default_plugin = hardware_plugin

            # Change boot order if supported and needed
            if is_supported(host) and boot_order != Config.get("foreman_default_boot_order"):
                if not await self.hardware_dispatcher.change_boot(boot_order, interfaces_path):
                    logger.error(f"Could not set boot order for {host}.")
                    return False
                # wait 10 minutes for the boot order job to complete
                await asyncio.sleep(600)

            return True
        except Exception as e:
            logger.error(f"Could not initialize hardware for {host}: {e}")
            return False

    async def prepare_host_provisioning(
        self, host: str, cloud: str, os_type: str, semaphore: asyncio.Semaphore
    ) -> bool:
        """Prepare host for provisioning via Foreman"""
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

            owner_id = await foreman.get_user_id(cloud)
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

    async def power_on_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """Power on a host"""
        await self._setup_hardware_for_host(host, rack, uloc, blade)
        return await self.hardware_dispatcher.set_power_state("on")

    async def power_off_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """Power off a host"""
        await self._setup_hardware_for_host(host, rack, uloc, blade)
        return await self.hardware_dispatcher.set_power_state("off")

    async def cleanup_virtual_media(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """Cleanup virtual media and remote images"""
        await self._setup_hardware_for_host(host, rack, uloc, blade)

        success = True
        if not await self.hardware_dispatcher.unmount_virtual_media():
            logger.warning(f"Could not unmount virtual media for {host}.")
            success = False

        if not await self.hardware_dispatcher.detach_remote_image():
            logger.warning(f"Could not detach remote image for {host}.")
            success = False

        return success

    def get_release_info(self) -> Dict[str, Any]:
        """Get release plugin information"""
        return {
            "name": "standard",
            "description": "Standard release plugin with hardware and provisioner support",
            "supports_hardware": True,
            "supports_provisioner": True,
            "supports_pdu": Config.pdu_management,
        }

    # Helper methods
    async def _setup_hardware_for_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """Setup hardware dispatcher for a specific host"""
        try:
            hardware_plugin = BadfishHardwarePlugin(host, rack, uloc, blade)
            await hardware_plugin.init()
            self.hardware_dispatcher._default_plugin = hardware_plugin
            return True
        except Exception as e:
            logger.error(f"Could not initialize hardware for {host}: {e}")
            return False

    async def _reboot_for_rebuild(self, host: str, host_obj, boot_order: str, interfaces_path: str) -> bool:
        """Reboot host for rebuild"""
        # Set boot to default order if needed
        if boot_order != Config.get("foreman_default_boot_order"):
            if not await self.hardware_dispatcher.boot_to_type(
                Config.get("foreman_default_boot_order"),
                interfaces_path,
            ):
                logger.error(f"Error setting PXE boot on {host}.")
                return False

        # Reboot
        if not await self.hardware_dispatcher.reboot_server(graceful=False):
            logger.error(f"Error rebooting server: {host}")
            return False

        return True

    def _update_host_on_failure(self, host_obj) -> None:
        """Update host with failure data"""
        update_data = {
            "build": False,
            "validated": False,
            "switch_config_applied": False,
        }
        self.quads.update_host(host_obj.name, update_data)
