from src.quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Optional, Dict, Any
import asyncio


class MigrationPlugin(BasePlugin):
    """Interface for host migration/rebuild plugins"""

    @abstractmethod
    async def move_and_rebuild(
        self, host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
    ) -> bool:
        """
        Move a host to a new cloud and optionally rebuild it.

        Args:
            host: Hostname to move
            new_cloud: Target cloud name
            semaphore: Async semaphore for concurrency control
            rebuild: Whether to rebuild the host

        Returns:
            bool: True if move/rebuild successful, False otherwise
        """
        pass

    @abstractmethod
    async def prepare_host_hardware(
        self, host: str, rack: str, uloc: str, blade: str, boot_order: str, interfaces_path: str
    ) -> bool:
        """
        Prepare host hardware for rebuild (boot order, power management).

        Args:
            host: Hostname
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier
            boot_order: Boot order configuration
            interfaces_path: Path to interfaces config

        Returns:
            bool: True if hardware preparation successful
        """
        pass

    @abstractmethod
    async def prepare_host_provisioning(
        self, host: str, cloud: str, os_type: str, semaphore: asyncio.Semaphore
    ) -> bool:
        """
        Prepare host for provisioning (Foreman setup, etc.).

        Args:
            host: Hostname
            cloud: Cloud name
            os_type: Operating system type
            semaphore: Async semaphore

        Returns:
            bool: True if provisioning preparation successful
        """
        pass

    @abstractmethod
    async def power_on_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """
        Power on a host.

        Args:
            host: Hostname
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier

        Returns:
            bool: True if power on successful
        """
        pass

    @abstractmethod
    async def power_off_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """
        Power off a host.

        Args:
            host: Hostname
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier

        Returns:
            bool: True if power off successful
        """
        pass

    @abstractmethod
    async def cleanup_virtual_media(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """
        Cleanup virtual media and remote images.

        Args:
            host: Hostname
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier

        Returns:
            bool: True if cleanup successful
        """
        pass

    @abstractmethod
    def get_migration_info(self) -> Dict[str, Any]:
        """
        Get migration plugin information.

        Returns:
            dict: Migration plugin capabilities and status
        """
        pass
