import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.cloud import CloudPlugin, CloudInstance
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class CloudDispatcher(SinglePluginDispatcher[CloudPlugin]):

    def __init__(self, plugin_manager: PluginManager, provider_name: str):
        if not provider_name:
            raise ValueError(
                "Cloud provider name is REQUIRED. "
                "Must explicitly specify which provider to use (e.g., 'aws', 'azure', 'gcp'). "
                "This prevents accidental cloud costs and ensures compliance."
            )

        super().__init__(plugin_manager, CloudPlugin, "Cloud", plugin_name=provider_name)

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
        if not self._default_plugin:
            logger.error("No cloud provider plugin enabled")
            return {"cloud_instances": [], "provider": None, "estimated_cost": 0.0}

        logger.info(f"Provisioning {count} cloud instances for {cloud_name} via {self._default_plugin.name}")

        cloud_instances = await self._provision_cloud_instances(
            self._default_plugin, count, instance_type, cloud_name, owner, start_date, end_date
        )

        result = {
            "cloud_instances": cloud_instances,
        }

        logger.info(
            f"Provisioned {len(cloud_instances)}/{count} cloud instances. "
            f"Estimated cost: ${result['estimated_cost']:.2f}"
        )

        return result

    async def _provision_cloud_instances(
        self,
        provider: CloudPlugin,
        count: int,
        instance_type: str,
        cloud_name: str,
        owner: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CloudInstance]:
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
        result = {"terminated": 0, "failed": 0}

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
    return CloudDispatcher(plugin_manager, provider_name=provider_name)
