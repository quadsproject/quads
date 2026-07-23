from typing import Optional

import aiohttp

from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.plugins.manager import PluginManager


class LibvirtHardwarePlugin(HardwarePlugin):
    """
    Hardware plugin for libvirt VMs via sushy-emulator.

    The host's rack field holds the hypervisor FQDN, which is used to look up
    the sushy-emulator URL from plugins.libvirt.hypervisors in plugins.yml.
    VM identity is resolved dynamically by matching the host name against
    the Name/HostName fields returned by the sushy /redfish/v1/Systems listing.
    """

    name = "libvirt"
    version = "1.0.0"
    description = "Libvirt hardware plugin via sushy-emulator Redfish API"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.hypervisors = self.config.get("hypervisors", {})
        self.sushy_url: Optional[str] = None
        self.system_uri: Optional[str] = None
        return True

    async def init(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        self.host = host
        self.sushy_url = self.hypervisors.get(rack)
        if not self.sushy_url:
            raise RuntimeError(f"No sushy-emulator URL configured for hypervisor '{rack}'")

        self.system_uri = await self._discover_system_uri(host)
        if not self.system_uri:
            raise RuntimeError(f"VM '{host}' not found via sushy-emulator at {self.sushy_url}")

        self.logger.info(f"Resolved {host} -> {self.system_uri}")
        return True

    async def _discover_system_uri(self, host: str) -> Optional[str]:
        """Walk /redfish/v1/Systems and match by Name or HostName."""
        short = host.split(".")[0]
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.sushy_url}/redfish/v1/Systems",
                ssl=False,
            ) as resp:
                index = await resp.json(content_type=None)

            for member in index.get("Members", []):
                href = member.get("@odata.id", "")
                system_url = f"{self.sushy_url}{href}"
                async with session.get(system_url, ssl=False) as resp:
                    sdata = await resp.json(content_type=None)

                vm_name = sdata.get("Name", "")
                vm_host = sdata.get("HostName", "")
                if host in (vm_name, vm_host) or short == vm_name.split(".")[0]:
                    return system_url

        return None

    async def _reset(self, reset_type: str) -> None:
        action_uri = f"{self.system_uri}/Actions/ComputerSystem.Reset"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                action_uri,
                json={"ResetType": reset_type},
                ssl=False,
            ) as resp:
                if resp.status not in (200, 202, 204):
                    text = await resp.text()
                    raise RuntimeError(f"Reset {reset_type} failed ({resp.status}): {text}")

    async def set_power_state(self, state: str) -> None:
        reset_type = "On" if state == "on" else "ForceOff"
        await self._reset(reset_type)

    async def get_power_state(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.system_uri, ssl=False) as resp:
                data = await resp.json(content_type=None)
        return data.get("PowerState", "Unknown")

    async def reboot_server(self, graceful: bool = False) -> bool:
        try:
            power_state = await self.get_power_state()
            if power_state.lower() == "off":
                reset_type = "On"
            else:
                reset_type = "GracefulRestart" if graceful else "ForceRestart"
            await self._reset(reset_type)
            return True
        except Exception as e:
            self.logger.error(f"Reboot of {self.host} failed: {e}")
            return False

    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """Set one-shot PXE boot override. host_type and interfaces_path are unused for VMs."""
        payload = {
            "Boot": {
                "BootSourceOverrideEnabled": "Once",
                "BootSourceOverrideTarget": "Pxe",
            }
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(
                    self.system_uri,
                    json=payload,
                    ssl=False,
                ) as resp:
                    if resp.status not in (200, 202, 204):
                        text = await resp.text()
                        raise RuntimeError(f"Boot override failed ({resp.status}): {text}")
            return True
        except Exception as e:
            self.logger.error(f"boot_to_type failed for {self.host}: {e}")
            return False

    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        # VMs have no complex boot-order profiles; treat any change as PXE once.
        return await self.boot_to_type(boot_order, interfaces_path)

    async def set_next_boot_pxe(self) -> None:
        await self.boot_to_type("pxe", "")

    async def unmount_virtual_media(self) -> bool:
        return True

    async def detach_remote_image(self) -> bool:
        return True

    def get_vendor(self) -> str:
        return "Libvirt"
