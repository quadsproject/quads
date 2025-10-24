#!/usr/bin/env python3
"""
Cloud Provider Dispatcher - Intelligent routing between bare metal and cloud

Automatically provisions from cloud providers when local bare metal is exhausted.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from quads.plugins.dispatchers.base import BaseDispatcher
from quads.plugins.interfaces.cloud_provider import CloudProviderPlugin, CloudInstance, InstanceState
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class CloudDispatcher(BaseDispatcher[CloudProviderPlugin]):
    """
    Intelligently routes provisioning between bare metal and cloud.

    Strategy:
    1. Try to allocate from local bare metal first (no cost)
    2. If local is exhausted, check enabled cloud providers
    3. Select best cloud provider based on:
       - Available capacity
       - Cost
       - Region preferences
    4. Track cloud instances for billing/lifecycle
    """

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, CloudProviderPlugin, "CloudProvider")
        self.cloud_preference_order = []  # Populated from config

    async def check_local_availability(
        self, count: int, start_date: datetime, end_date: datetime, **requirements
    ) -> int:
        """
        Check how many hosts are available from local bare metal.

        This should query the QUADS scheduler/database.

        Args:
            count: Number of hosts needed
            start_date: Assignment start date
            end_date: Assignment end date
            **requirements: Host requirements (model, memory, etc.)

        Returns:
            Number of available local hosts (0 to count)
        """
        # TODO: Integrate with existing QUADS scheduling logic
        # For now, this is a placeholder that would call:
        # from quads.server.dao.host import HostDao
        # from quads.server.dao.schedule import ScheduleDao
        #
        # available = ScheduleDao.get_available_hosts(
        #     start=start_date,
        #     end=end_date,
        #     count=count,
        #     **requirements
        # )
        # return len(available)

        logger.info(f"Checking local availability for {count} hosts " f"from {start_date} to {end_date}")
        # Placeholder - would return actual available count
        return 0

    async def provision_resources(
        self,
        count: int,
        start_date: datetime,
        end_date: datetime,
        cloud_name: str,
        owner: str,
        instance_type: Optional[str] = None,
        **requirements,
    ) -> Dict[str, Any]:
        """
        Provision resources, intelligently choosing bare metal or cloud.

        Args:
            count: Number of hosts/instances needed
            start_date: Assignment start
            end_date: Assignment end
            cloud_name: QUADS cloud name
            owner: Assignment owner
            instance_type: Cloud instance type (if going to cloud)
            **requirements: Host/instance requirements

        Returns:
            {
                "local_hosts": ["host01", "host02"],
                "cloud_instances": [CloudInstance, CloudInstance],
                "provider": "aws" or None,
                "estimated_cost": 123.45,
                "strategy": "local_only" | "cloud_only" | "hybrid"
            }
        """
        result = {"local_hosts": [], "cloud_instances": [], "provider": None, "estimated_cost": 0.0, "strategy": None}

        # Step 1: Check local bare metal availability
        local_available = await self.check_local_availability(count, start_date, end_date, **requirements)

        if local_available >= count:
            # All needs met by local bare metal
            logger.info(f"Sufficient local capacity: {local_available}/{count}")
            result["strategy"] = "local_only"
            # TODO: Actually reserve the local hosts
            # result["local_hosts"] = ScheduleDao.reserve_hosts(...)
            return result

        # Step 2: We need cloud resources
        cloud_needed = count - local_available

        logger.info(
            f"Local capacity insufficient: {local_available}/{count} available. " f"Need {cloud_needed} from cloud."
        )

        # Step 3: Find best cloud provider
        provider_info = await self._select_best_cloud_provider(
            cloud_needed, instance_type, start_date, end_date, **requirements
        )

        if not provider_info:
            logger.error("No cloud providers available to fulfill request")
            return result

        provider_plugin = provider_info["plugin"]
        selected_instance_type = provider_info["instance_type"]

        logger.info(
            f"Selected cloud provider: {provider_plugin.name} " f"with instance type: {selected_instance_type}"
        )

        # Step 4: Provision cloud instances
        cloud_instances = await self._provision_cloud_instances(
            provider_plugin, cloud_needed, selected_instance_type, cloud_name, owner, start_date, end_date
        )

        # Step 5: Build result
        result["cloud_instances"] = cloud_instances
        result["provider"] = provider_plugin.name
        result["estimated_cost"] = provider_info["estimated_cost"]

        if local_available > 0:
            result["strategy"] = "hybrid"
            # TODO: Reserve local hosts
            # result["local_hosts"] = ScheduleDao.reserve_hosts(...)
        else:
            result["strategy"] = "cloud_only"

        logger.info(
            f"Provisioned {len(cloud_instances)} cloud instances "
            f"+ {local_available} local hosts. "
            f"Estimated cost: ${result['estimated_cost']:.2f}"
        )

        return result

    async def _select_best_cloud_provider(
        self, count: int, instance_type: Optional[str], start_date: datetime, end_date: datetime, **requirements
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best cloud provider based on capacity, cost, and preferences.

        Returns:
            {
                "plugin": CloudProviderPlugin,
                "instance_type": "t3.medium",
                "estimated_cost": 123.45
            }
        """
        if not self._plugins:
            return None

        hours = int((end_date - start_date).total_seconds() / 3600)
        candidates = []

        for plugin in self._plugins:
            # Check capacity
            capacity = await plugin.get_available_capacity(instance_type)
            if capacity < count:
                logger.debug(f"{plugin.name} has insufficient capacity: {capacity}/{count}")
                continue

            # Check quota
            if not await plugin.validate_quota(instance_type or "default", count):
                logger.debug(f"{plugin.name} quota exceeded")
                continue

            # Get instance types if not specified
            if not instance_type:
                # Find cheapest instance type that meets requirements
                types = await plugin.get_instance_types(
                    min_vcpus=requirements.get("min_vcpus"), min_memory_gb=requirements.get("min_memory_gb")
                )
                if not types:
                    continue
                # Sort by cost
                types.sort(key=lambda x: x["cost_per_hour"])
                selected_type = types[0]["name"]
            else:
                selected_type = instance_type

            # Estimate cost
            cost_breakdown = await plugin.estimate_cost(selected_type, hours)
            total_cost = cost_breakdown["total"] * count

            candidates.append(
                {
                    "plugin": plugin,
                    "instance_type": selected_type,
                    "estimated_cost": total_cost,
                    "cost_per_hour": cost_breakdown["total"] / hours,
                }
            )

        if not candidates:
            return None

        # Sort by cost (cheapest first)
        candidates.sort(key=lambda x: x["estimated_cost"])

        # Could add preference logic here based on config
        # For now, return cheapest option
        return candidates[0]

    async def _provision_cloud_instances(
        self,
        provider: CloudProviderPlugin,
        count: int,
        instance_type: str,
        cloud_name: str,
        owner: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CloudInstance]:
        """Provision multiple cloud instances"""
        instances = []

        for i in range(count):
            name = f"{cloud_name}-cloud-{i + 1}"
            tags = {
                "quads_cloud": cloud_name,
                "quads_owner": owner,
                "quads_start": start_date.isoformat(),
                "quads_end": end_date.isoformat(),
                "quads_type": "cloud_instance",
            }

            logger.info(f"Creating cloud instance: {name} ({instance_type})")

            instance = await provider.create_instance(name=name, instance_type=instance_type, tags=tags)

            if instance:
                instances.append(instance)
                logger.info(f"Created instance {instance.instance_id} at {instance.public_ip}")
            else:
                logger.error(f"Failed to create instance {name}")

        return instances

    async def terminate_cloud_instances(self, cloud_name: str) -> Dict[str, int]:
        """
        Terminate all cloud instances for a cloud assignment.

        Args:
            cloud_name: QUADS cloud name

        Returns:
            {
                "terminated": 5,
                "failed": 1
            }
        """
        result = {"terminated": 0, "failed": 0}

        # Get instances from all providers
        for plugin in self._plugins:
            instances = await plugin.list_instances(tags={"quads_cloud": cloud_name})

            for instance in instances:
                logger.info(f"Terminating {plugin.name} instance: {instance.instance_id}")

                success = await plugin.terminate_instance(instance.instance_id)
                if success:
                    result["terminated"] += 1
                else:
                    result["failed"] += 1

        logger.info(
            f"Cloud cleanup for {cloud_name}: " f"{result['terminated']} terminated, {result['failed']} failed"
        )

        return result

    async def get_cloud_cost_report(
        self,
        cloud_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get cost report for cloud instances.

        Args:
            cloud_name: Optional filter by cloud
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            {
                "total_cost": 1234.56,
                "by_provider": {
                    "aws": 800.00,
                    "ibm_cloud": 434.56
                },
                "by_cloud": {
                    "cloud05": 500.00,
                    "cloud12": 734.56
                },
                "instance_count": 42
            }
        """
        report = {"total_cost": 0.0, "by_provider": {}, "by_cloud": {}, "instance_count": 0}

        for plugin in self._plugins:
            instances = await plugin.list_instances()

            provider_cost = 0.0

            for instance in instances:
                # Filter by cloud if specified
                if cloud_name and instance.metadata.get("tags", {}).get("quads_cloud") != cloud_name:
                    continue

                # Calculate runtime
                # TODO: Get actual runtime from instance metadata
                cost = instance.cost_per_hour or 0.0
                provider_cost += cost

                # Track by cloud
                inst_cloud = instance.metadata.get("tags", {}).get("quads_cloud", "unknown")
                report["by_cloud"][inst_cloud] = report["by_cloud"].get(inst_cloud, 0.0) + cost

                report["instance_count"] += 1

            report["by_provider"][plugin.name] = provider_cost
            report["total_cost"] += provider_cost

        return report


# Singleton instance
_dispatcher_instance: Optional[CloudDispatcher] = None


def get_cloud_dispatcher(plugin_manager: Optional[PluginManager] = None) -> CloudDispatcher:
    """Get the global CloudDispatcher instance"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize CloudDispatcher")
        _dispatcher_instance = CloudDispatcher(plugin_manager)

    return _dispatcher_instance
