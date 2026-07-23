"""
Standard Release Plugin - Default implementation for host release/rebuild
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from quads.config import Config
from quads.helpers.utils import is_libvirt, is_supermicro
from quads.plugins.builtin.hardware.libvirt import LibvirtHardwarePlugin
from quads.plugins.interfaces.release import ReleasePlugin
from quads.plugins.dispatchers import get_hardware_dispatcher, get_provisioner_dispatcher
from quads.quads_api import QuadsApi
from quads.tools.external.ipmi import IPMI
from quads.plugins.manager import PluginManager
from quads.server.models import Host


class StandardReleasePlugin(ReleasePlugin):
    """
    Standard release plugin implementing ReleasePlugin interface.

    Manages host release/rebuild orchestration.
    """

    name = "standard"
    version = "1.0.0"
    description = "Standard release plugin for moving and rebuilding hosts"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.quads = QuadsApi(Config)
        self.hardware_dispatcher = get_hardware_dispatcher(plugin_manager)
        self.provisioner_dispatcher = get_provisioner_dispatcher(plugin_manager)
        self.hardware_initialized = False
        return True

    async def _report_progress(self, schedule_id, status, message="", error_message=""):
        if not schedule_id:
            return
        try:
            data = {"status": status, "message": message}
            if error_message:
                data["error_message"] = error_message
            await asyncio.to_thread(self.quads.update_move_status, schedule_id, data)
        except Exception as e:
            self.logger.warning(f"Failed to report progress: {e}")

    async def _configure_and_verify_ipmi(
        self,
        host: str,
        admin_username: str,
        admin_password: str,
        new_password: str,
    ) -> Optional[IPMI]:
        """Set and verify IPMI credentials for the tenant user with retry.

        Returns the admin-credential IPMI instance on success, None on failure.
        """
        config_standard = Config.plugins.get("standard", {})
        max_retries = config_standard.get("ipmi_credential_retries", 3)
        retry_delay = config_standard.get("ipmi_credential_retry_delay", 10)

        for attempt in range(1, max_retries + 1):
            ipmi = IPMI(host, admin_username, admin_password, logger=self.logger)
            if not await ipmi.configure_user(Config["ipmi_cloud_username_id"], new_password):
                self.logger.warning(f"IPMI credential set failed for {host} (attempt {attempt}/{max_retries})")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                continue

            verify_ipmi = IPMI(host, Config["ipmi_cloud_username"], new_password, logger=self.logger)
            if await verify_ipmi.verify_credentials():
                return ipmi

            self.logger.warning(f"IPMI credential verification failed for {host} (attempt {attempt}/{max_retries})")
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

        self.logger.error(f"Failed to set and verify IPMI credentials for {host} after {max_retries} attempts")
        return None

    async def move_and_rebuild(
        self,
        host: str,
        new_cloud: str,
        semaphore: asyncio.Semaphore,
        rebuild: bool = False,
        schedule_id: Optional[int] = None,
    ) -> bool:
        """Move a host to a new cloud and optionally rebuild it"""
        build_start = datetime.now()
        self.logger.debug(f"Moving and rebuilding host: {host}")

        # Check if host is untouchable
        untouchable_hosts = Config["untouchable_hosts"]
        if host in untouchable_hosts:
            self.logger.error(f"Host {host} is in untouchable hosts list")
            return False

        host_obj = self.quads.get_host(host)
        target_cloud = self.quads.get_cloud(new_cloud)

        _is_libvirt = is_libvirt(host_obj)
        _is_supermicro = is_supermicro(host)

        # Get boot order and ticket info
        boot_order = Config.plugins["foreman"]["default_boot_order"]
        ticket = ""
        _assignment = self.quads.get_active_cloud_assignment(target_cloud.name)
        if _assignment:
            ticket = _assignment.ticket
            if _assignment.boot_order:
                boot_order = _assignment.boot_order

        # Configure IPMI credentials -- libvirt VMs have no BMC
        if not _is_libvirt:
            config_ipmi = Config["plugins"]["badfish"]
            ipmi_username = config_ipmi["ipmi_username"]
            ipmi_password = config_ipmi["ipmi_password"]
            ipmi_new_pass = f"{Config['infra_location']}@{ticket}" if ticket else ipmi_password

            ipmi = await self._configure_and_verify_ipmi(host, ipmi_username, ipmi_password, ipmi_new_pass)
            if ipmi is None:
                self._update_host_on_failure(
                    host_obj,
                    schedule_id=schedule_id,
                    error_message="Failed at ipmi_config",
                )
                return False

            await self._report_progress(schedule_id, "ipmi_config", "IPMI credentials configured and verified")

            if rebuild:
                if not await ipmi.disable_user(Config["ipmi_cloud_username_id"]):
                    self.logger.warning(f"Failed to gate IPMI user for {host}, continuing")
                else:
                    self.logger.info(f"IPMI user gated for {host} until validation completes")

        _is_supermicro = is_supermicro(host)

        if rebuild and target_cloud.name != host_obj.default_cloud.name:
            # Handle PDU management if configured
            if Config.pdu_management:
                # TODO: pdu management
                pass

            if _is_libvirt:
                os_type = Config.plugins["foreman"]["default_os"]
                if _assignment and _assignment.ostype:
                    os_type = _assignment.ostype

                libvirt_plugin = LibvirtHardwarePlugin(Config.plugins.get("libvirt", {}))
                libvirt_plugin.initialize()
                try:
                    await libvirt_plugin.init(host, host_obj.rack, host_obj.uloc, host_obj.blade)
                except Exception as e:
                    self.logger.error(f"Could not initialize libvirt plugin for {host}: {e}")
                    self._update_host_on_failure(
                        host_obj, schedule_id=schedule_id, error_message="Failed at libvirt init"
                    )
                    return False

                await self._report_progress(schedule_id, "provisioning", "Preparing provisioner")
                if not await self.provisioner_dispatcher.prepare_host_provisioning(host, new_cloud, os_type):
                    self._update_host_on_failure(
                        host_obj, schedule_id=schedule_id, error_message="Failed at provisioning"
                    )
                    return False

                await self._report_progress(schedule_id, "reboot", "PXE boot and power cycle")
                if not await libvirt_plugin.boot_to_type("foreman", ""):
                    self._update_host_on_failure(
                        host_obj, schedule_id=schedule_id, error_message="Failed at boot override"
                    )
                    return False
                if not await libvirt_plugin.reboot_server(graceful=False):
                    self._update_host_on_failure(host_obj, schedule_id=schedule_id, error_message="Failed at reboot")
                    return False

            elif _is_supermicro:
                # No Badfish for Supermicro -- use raw ipmitool
                os_type = Config.plugins["foreman"]["default_os"]
                if _assignment and _assignment.ostype:
                    os_type = _assignment.ostype

                await self._report_progress(schedule_id, "provisioning", "Preparing provisioner")
                if not await self.provisioner_dispatcher.prepare_host_provisioning(host, new_cloud, os_type):
                    self._update_host_on_failure(
                        host_obj, schedule_id=schedule_id, error_message="Failed at provisioning"
                    )
                    return False

                await self._report_progress(schedule_id, "reboot", "PXE boot and power cycle")
                if not await ipmi.pxe_persistent():
                    self.logger.error(f"There was something wrong setting PXE flag or resetting IPMI on {host}.")
                    self._update_host_on_failure(host_obj, schedule_id=schedule_id, error_message="Failed at power_on")
                    return False
            else:
                # Dell/HPE: serialize Badfish calls via semaphore so concurrent move
                # tasks don't interleave on the shared singleton dispatcher.
                async with semaphore:
                    self.hardware_initialized = False
                    ok, vendor = await self.prepare_host_hardware(
                        host_obj, boot_order, Config.get("badfish_interfaces_path")
                    )
                    if not ok:
                        self._update_host_on_failure(
                            host_obj, schedule_id=schedule_id, error_message="Failed at hardware_prep"
                        )
                        return False
                    await self._report_progress(schedule_id, "hardware_prep", "Hardware prepared")

                    if not await self.power_on_host(host_obj):
                        self.logger.error(f"Failed to power on {host}")
                        self._update_host_on_failure(
                            host_obj, schedule_id=schedule_id, error_message="Failed at power_on"
                        )
                        return False
                    await self._report_progress(schedule_id, "power_on", "Host powered on")

                    if vendor is None:
                        vendor = self.hardware_dispatcher.get_vendor()

                    os_type = Config.plugins["foreman"]["default_os"]
                    if _assignment and _assignment.ostype:
                        os_type = _assignment.ostype

                    if not await self.provisioner_dispatcher.prepare_host_provisioning(host, new_cloud, os_type):
                        self._update_host_on_failure(
                            host_obj, schedule_id=schedule_id, error_message="Failed at provisioning"
                        )
                        return False
                    await self._report_progress(schedule_id, "provisioning", "Provisioner ready")

                    await self.cleanup_virtual_media(host_obj)
                    await self._report_progress(schedule_id, "cleanup", "Virtual media cleaned")

                    if vendor == "Dell":
                        if not await self.reboot_for_rebuild(host_obj, Config.get("badfish_interfaces_path")):
                            self._update_host_on_failure(
                                host_obj, schedule_id=schedule_id, error_message="Failed at reboot"
                            )
                            return False
                    else:
                        if not await ipmi.pxe_persistent():
                            self.logger.error(
                                f"There was something wrong setting PXE flag or resetting IPMI on {host}."
                            )
                            self._update_host_on_failure(
                                host_obj, schedule_id=schedule_id, error_message="Failed at reboot"
                            )
                            return False
                    await self._report_progress(schedule_id, "reboot", "Rebooting for rebuild")

        # Power off if moving back to default cloud
        if target_cloud.name == host_obj.default_cloud.name:
            if _is_libvirt:
                libvirt_plugin = LibvirtHardwarePlugin(Config.plugins.get("libvirt", {}))
                libvirt_plugin.initialize()
                try:
                    await libvirt_plugin.init(host, host_obj.rack, host_obj.uloc, host_obj.blade)
                    await libvirt_plugin.set_power_state("off")
                except Exception as e:
                    self.logger.error(f"Failed to power off {host}: {e}")
                    self._update_host_on_failure(
                        host_obj, schedule_id=schedule_id, error_message="Failed at power_off"
                    )
                    return False
            elif _is_supermicro:
                try:
                    await ipmi.execute(["chassis", "power", "off"])
                except Exception as e:
                    self.logger.error(f"Failed to power off {host}: {e}")
                    self._update_host_on_failure(host_obj, schedule_id=schedule_id, error_message="Failed at power_on")
                    return False
            else:
                async with semaphore:
                    self.hardware_initialized = False
                    if not await self.power_off_host(host_obj):
                        self.logger.error(f"Failed to power off {host}")
                        self._update_host_on_failure(
                            host_obj, schedule_id=schedule_id, error_message="Failed at power_on"
                        )
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
            "overcloud": True,
            "last_build": datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "validated": False,
        }
        self.quads.update_host(host_obj.name, success_data)
        await self._report_progress(schedule_id, "post_install", "Records updated")

        return True

    async def prepare_host_hardware(
        self, host_obj: Host, boot_order: str, interfaces_path: str
    ) -> tuple[bool, Optional[str]]:
        """Prepare host hardware for rebuild. Returns (success, vendor)."""
        try:
            vendor = None
            if boot_order != Config.plugins["foreman"]["default_boot_order"]:
                if not self.hardware_initialized:
                    self.hardware_initialized = await self.hardware_dispatcher.init(
                        host_obj.name, host_obj.rack, host_obj.uloc, host_obj.blade
                    )
                if not self.hardware_initialized:
                    return False, None
                vendor = self.hardware_dispatcher.get_vendor()  # sync read after init, no yield between
                if vendor == "Dell":
                    if not await self.hardware_dispatcher.change_boot(boot_order, interfaces_path):
                        self.logger.error(f"Could not set boot order for {host_obj.name}.")
                        return False, vendor
                    # TODO: replace with a proper wait_for_job() poll on the iDRAC job queue
                    # instead of a fixed 600s sleep
                    await asyncio.sleep(600)

            return True, vendor
        except Exception as e:
            self.logger.error(f"Could not initialize hardware for {host_obj.name}: {e}")
            return False, None

    async def power_on_host(self, host_obj: Host) -> bool:
        """Power on a host"""
        if not self.hardware_initialized:
            self.hardware_initialized = await self.hardware_dispatcher.init(
                host_obj.name, host_obj.rack, host_obj.uloc, host_obj.blade
            )
        return await self.hardware_dispatcher.set_power_state("on")

    async def power_off_host(self, host_obj: Host) -> bool:
        """Power off a host"""
        if not self.hardware_initialized:
            self.hardware_initialized = await self.hardware_dispatcher.init(
                host_obj.name, host_obj.rack, host_obj.uloc, host_obj.blade
            )
        return await self.hardware_dispatcher.set_power_state("off")

    async def cleanup_virtual_media(self, host_obj) -> bool:
        """Cleanup virtual media and remote images"""

        success = True
        if not self.hardware_initialized:
            self.hardware_initialized = await self.hardware_dispatcher.init(
                host_obj.name, host_obj.rack, host_obj.uloc, host_obj.blade
            )
        if not await self.hardware_dispatcher.unmount_virtual_media():
            self.logger.warning(f"Could not unmount virtual media for {host_obj.name}.")
            success = False

        if not await self.hardware_dispatcher.detach_remote_image():
            self.logger.warning(f"Could not detach remote image for {host_obj.name}.")
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

    async def _is_one_time_boot_set(self, host_obj: Host) -> bool:
        try:
            boot_mode = await self.hardware_dispatcher.get_bios_attribute("BootMode")
            boot_seq = "UefiBootSeq" if boot_mode == "Uefi" else "BootSeq"

            current_mode = await self.hardware_dispatcher.get_bios_attribute("OneTimeBootMode")
            current_device = await self.hardware_dispatcher.get_bios_attribute(f"OneTime{boot_seq}Dev")

            if current_mode == f"OneTime{boot_seq}" and current_device:
                self.logger.info(
                    "One-time boot already set to %s on %s, skipping."
                    % (current_device, host_obj.name)
                )
                return True
        except Exception as exc:
            self.logger.warning(
                "Could not determine one-time boot state for %s, proceeding with set: %s"
                % (host_obj.name, exc)
            )
        return False

    async def reboot_for_rebuild(self, host_obj: Host, interfaces_path: str) -> bool:
        """Reboot host for rebuild"""
        if not self.hardware_initialized:
            self.hardware_initialized = await self.hardware_dispatcher.init(
                host_obj.name, host_obj.rack, host_obj.uloc, host_obj.blade
            )
        if not self.hardware_initialized:
            self.logger.error(f"Hardware not initialized for {host_obj.name}")
            return False

        if not await self._is_one_time_boot_set(host_obj):
            if not await self.hardware_dispatcher.boot_to_type(
                Config.plugins["foreman"]["default_boot_order"],
                interfaces_path,
            ):
                self.logger.error(f"Error setting PXE boot on {host_obj.name}.")
                return False

        if not await self.hardware_dispatcher.reboot_server(graceful=False):
            self.logger.error(f"Error rebooting server: {host_obj.name}")
            return False

        return True

    def _update_host_on_failure(self, host_obj, schedule_id=None, error_message="Move failed") -> None:
        """Update host with failure data"""
        update_data = {
            "build": False,
            "validated": False,
        }
        if not is_libvirt(host_obj):
            update_data["switch_config_applied"] = False
        self.quads.update_host(host_obj.name, update_data)
        if schedule_id:
            try:
                self.quads.update_move_status(
                    schedule_id,
                    {"status": "failed", "error_message": error_message},
                )
            except Exception:
                pass
