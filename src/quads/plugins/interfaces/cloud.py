from abc import abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum
from quads.plugins.base import BasePlugin


class InstanceState(Enum):
    """Cloud instance states"""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    ERROR = "error"


class CloudInstance:
    """Represents a cloud instance"""

    def __init__(
        self,
        instance_id: str,
        provider: str,
        instance_type: str,
        state: InstanceState,
        public_ip: Optional[str] = None,
        private_ip: Optional[str] = None,
        region: Optional[str] = None,
        cost_per_hour: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.instance_id = instance_id
        self.provider = provider
        self.instance_type = instance_type
        self.state = state
        self.public_ip = public_ip
        self.private_ip = private_ip
        self.region = region
        self.cost_per_hour = cost_per_hour
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "instance_id": self.instance_id,
            "provider": self.provider,
            "instance_type": self.instance_type,
            "state": self.state.value,
            "public_ip": self.public_ip,
            "private_ip": self.private_ip,
            "region": self.region,
            "cost_per_hour": self.cost_per_hour,
            "metadata": self.metadata,
        }


class CloudPlugin(BasePlugin):
    """
    Interface for cloud provider plugins.

    Allows provisioning VMs/instances from public cloud providers
    when local bare metal is unavailable.
    """

    @abstractmethod
    async def get_available_capacity(self, instance_type: Optional[str] = None, region: Optional[str] = None) -> int:
        """
        Get number of instances that can be provisioned.

        Args:
            instance_type: Optional filter by instance type
            region: Optional filter by region

        Returns:
            Number of instances available (may be limited by quota)
        """
        pass

    @abstractmethod
    async def create_instance(
        self,
        name: str,
        instance_type: str,
        image_id: Optional[str] = None,
        region: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Optional[CloudInstance]:
        """
        Create a new cloud instance.

        Args:
            name: Instance name/hostname
            instance_type: Instance type (e.g., "t3.medium", "cx2-2x4")
            image_id: OS image ID (defaults to config)
            region: Region to provision in (defaults to config)
            tags: Key-value tags for the instance
            **kwargs: Provider-specific parameters

        Returns:
            CloudInstance object or None on failure
        """
        pass

    @abstractmethod
    async def start_instance(self, instance_id: str) -> bool:
        """
        Start a stopped instance.

        Args:
            instance_id: Cloud provider instance ID

        Returns:
            True if started successfully
        """
        pass

    @abstractmethod
    async def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a running instance (keeps storage, stops compute charges).

        Args:
            instance_id: Cloud provider instance ID

        Returns:
            True if stopped successfully
        """
        pass

    @abstractmethod
    async def terminate_instance(self, instance_id: str) -> bool:
        """
        Terminate an instance (deletes everything).

        Args:
            instance_id: Cloud provider instance ID

        Returns:
            True if terminated successfully
        """
        pass

    @abstractmethod
    async def get_instance(self, instance_id: str) -> Optional[CloudInstance]:
        """
        Get instance details.

        Args:
            instance_id: Cloud provider instance ID

        Returns:
            CloudInstance object or None if not found
        """
        pass

    @abstractmethod
    async def list_instances(
        self, tags: Optional[Dict[str, str]] = None, state: Optional[InstanceState] = None
    ) -> List[CloudInstance]:
        """
        List instances, optionally filtered.

        Args:
            tags: Filter by tags
            state: Filter by state

        Returns:
            List of CloudInstance objects
        """
        pass

    @abstractmethod
    async def get_instance_types(
        self, min_vcpus: Optional[int] = None, min_memory_gb: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available instance types that match requirements.

        Args:
            min_vcpus: Minimum vCPUs required
            min_memory_gb: Minimum memory in GB required

        Returns:
            List of instance type specifications
            [
                {
                    "name": "t3.medium",
                    "vcpus": 2,
                    "memory_gb": 4,
                    "cost_per_hour": 0.0416
                },
                ...
            ]
        """
        pass

    @abstractmethod
    async def estimate_cost(self, instance_type: str, hours: int, region: Optional[str] = None) -> Dict[str, float]:
        """
        Estimate cost for running an instance.

        Args:
            instance_type: Instance type
            hours: Number of hours
            region: Region (defaults to configured region)

        Returns:
            Cost breakdown:
            {
                "compute": 10.00,
                "storage": 2.50,
                "network": 1.00,
                "total": 13.50
            }
        """
        pass
