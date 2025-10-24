#!/usr/bin/env python3
import asyncio
import logging

from quads.plugins.dispatchers.release import get_release_dispatcher
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize plugin manager and release dispatcher
plugin_manager = PluginManager()
release_dispatcher = get_release_dispatcher(plugin_manager)


async def move_and_rebuild(
    host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
) -> bool:  # pragma: no cover
    """
    Move a host to a new cloud and optionally rebuild it.

    This function now uses the release plugin dispatcher to handle
    the actual release logic, making it pluggable and extensible.

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
        return await release_dispatcher.move_and_rebuild(host, new_cloud, semaphore, rebuild)
    except Exception as ex:
        logger.error(f"Error in move_and_rebuild for {host}: {ex}")
        return False
