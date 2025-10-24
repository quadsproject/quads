#!/usr/bin/env python3
import asyncio
import logging

from quads.plugins.dispatchers.migration import get_migration_dispatcher
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize plugin manager and migration dispatcher
plugin_manager = PluginManager()
migration_dispatcher = get_migration_dispatcher(plugin_manager)


async def move_and_rebuild(
    host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
) -> bool:  # pragma: no cover
    """
    Move a host to a new cloud and optionally rebuild it.

    This function now uses the migration plugin dispatcher to handle
    the actual migration logic, making it pluggable and extensible.

    Args:
        host: Hostname to move
        new_cloud: Target cloud name
        semaphore: Async semaphore for concurrency control
        rebuild: Whether to rebuild the host

    Returns:
        bool: True if move/rebuild successful, False otherwise
    """
    logger.info(f"Moving {host} to {new_cloud} (rebuild={rebuild})")

    try:
        return await migration_dispatcher.move_and_rebuild(host, new_cloud, semaphore, rebuild)
    except Exception as ex:
        logger.error(f"Error in move_and_rebuild for {host}: {ex}")
        return False
