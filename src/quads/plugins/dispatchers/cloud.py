#!/usr/bin/env python3
"""
Cloud Provider Dispatcher - Routes cloud operations to enabled cloud provider

Uses SinglePluginDispatcher because cloud provisioning should be done via
ONE provider at a time (you don't provision the same instance on AWS and Azure
simultaneously).

This dispatcher handles cloud provider operations when the user/scheduler
has explicitly chosen to use cloud resources. It does NOT automatically
decide between bare metal and cloud - that decision is made upstream.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.cloud_provider import CloudProviderPlugin, CloudInstance, InstanceState
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class CloudDispatcher(SinglePluginDispatcher[CloudProviderPlugin]):
    """
    Dispatches cloud provider operations to the explicitly selected cloud provider.

    IMPORTANT: Cloud provider MUST be explicitly specified at initialization.
    There is NO default provider selection to prevent accidental cloud costs.

    This dispatcher is used when the user/scheduler has EXPLICITLY chosen
    to use cloud resources. It does NOT automatically decide between bare
    metal and cloud - that decision must be made upstream by the caller.

    The user must also explicitly choose WHICH cloud provider to use (AWS, Azure,
    GCP, etc.) to ensure cost control and compliance.

    This is a SinglePluginDispatcher - only ONE cloud provider is used at a time.

    Example:
        # REQUIRED: Must specify provider
        dispatcher = CloudDispatcher(plugin_manager, provider_name="aws")

        # ERROR: This will raise ValueError
        dispatcher = CloudDispatcher(plugin_manager)  # No provider specified!
    """

    def __init__(self, plugin_manager: PluginManager, provider_name: str):
        """
        Initialize cloud dispatcher with explicit provider selection.

        Args:
            plugin_manager: PluginManager instance
            provider_name: Cloud provider name (REQUIRED) - e.g., "aws", "azure", "gcp"

        Raises:
            ValueError: If provider_name is not specified or provider not found

        Example:
            dispatcher = CloudDispatcher(plugin_manager, provider_name="aws")
        """
        if not provider_name:
            raise ValueError(
                "Cloud provider name is REQUIRED. "
                "Must explicitly specify which provider to use (e.g., 'aws', 'azure', 'gcp'). "
                "This prevents accidental cloud costs and ensures compliance."
            )

        super().__init__(plugin_manager, CloudProviderPlugin, "CloudProvider", plugin_name=provider_name)

    async def provision_instances(
        self,
        count: int,
        cloud_name: str,
        owner: str,
        start_date: datetime,
        end_date: datetime,
        instance_type: Optional[str] = None,
        **requirements,
    ) -> Dict[str, Any]:
        """
        Provision cloud instances via the enabled cloud provider.

        This method should ONLY be called when the user/scheduler has
        explicitly decided to use cloud resources. This dispatcher does
        NOT make the decision between bare metal and cloud.

        Args:
            count: Number of cloud instances needed
            cloud_name: QUADS cloud name
            owner: Assignment owner
            start_date: Assignment start
            end_date: Assignment end
            instance_type: Cloud instance type (e.g., "t3.medium", "Standard_D2s_v3")
            **requirements: Instance requirements (vcpus, memory, etc.)

        Returns:
            {
                "cloud_instances": [CloudInstance, CloudInstance],
                "provider": "aws",
                "estimated_cost": 123.45
            }
        """
        if not self._default_plugin:
            logger.error("No cloud provider plugin enabled")
            return {"cloud_instances": [], "provider": None, "estimated_cost": 0.0}

        logger.info(f"Provisioning {count} cloud instances for {cloud_name} via {self._default_plugin.name}")

        # Step 1: Find best instance type and estimate cost
        provider_info = await self._select_best_cloud_provider(
            count, instance_type, start_date, end_date, **requirements
        )

        if not provider_info:
            logger.error("Unable to provision: cloud provider unavailable or quota exceeded")
            return {"cloud_instances": [], "provider": None, "estimated_cost": 0.0}

        provider_plugin = provider_info["plugin"]
        selected_instance_type = provider_info["instance_type"]

        logger.info(
            f"Selected cloud provider: {provider_plugin.name} with instance type: {selected_instance_type} "
            f"(estimated cost: ${provider_info['estimated_cost']:.2f})"
        )

        # Step 2: Provision cloud instances
        cloud_instances = await self._provision_cloud_instances(
            provider_plugin, count, selected_instance_type, cloud_name, owner, start_date, end_date
        )

        # Step 3: Build result
        result = {
            "cloud_instances": cloud_instances,
            "provider": provider_plugin.name,
            "estimated_cost": provider_info["estimated_cost"],
        }

        logger.info(
            f"Provisioned {len(cloud_instances)}/{count} cloud instances. "
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


def get_cloud_dispatcher(plugin_manager: PluginManager, provider_name: str) -> CloudDispatcher:
    """
    Create a CloudDispatcher instance for the specified provider.

    NOTE: Unlike other dispatchers, CloudDispatcher does NOT use a singleton pattern
    because cloud provider MUST be explicitly specified. Different parts of your code
    may need different providers.

    Args:
        plugin_manager: PluginManager instance
        provider_name: Cloud provider name (REQUIRED) - e.g., "aws", "azure", "gcp"

    Returns:
        New CloudDispatcher instance configured for the specified provider

    Raises:
        ValueError: If provider_name is not specified or provider not found

    Example:
        # Create dispatcher for specific provider
        aws_dispatcher = get_cloud_dispatcher(plugin_manager, "aws")
        azure_dispatcher = get_cloud_dispatcher(plugin_manager, "azure")

        # Provision on AWS
        await aws_dispatcher.provision_instances(count=5, ...)

        # Provision on Azure
        await azure_dispatcher.provision_instances(count=3, ...)

    Recommended:
        Create dispatcher instances directly for clarity:

        dispatcher = CloudDispatcher(plugin_manager, provider_name="aws")
    """
    return CloudDispatcher(plugin_manager, provider_name=provider_name)
