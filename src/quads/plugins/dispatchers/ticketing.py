import logging
from typing import Optional, Dict, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class TicketingDispatcher(SinglePluginDispatcher[TicketingPlugin]):
    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, TicketingPlugin, "Ticketing")

    async def create_ticket(
        self, summary: str, description: str, assignee: Optional[str] = None, labels: Optional[list] = None, **kwargs
    ) -> Optional[str]:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return None

        logger.info(f"Creating ticket via {self._default_plugin.name}: {summary}")
        try:
            return await self._default_plugin.create_ticket(summary, description, assignee, labels, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None

    async def update_ticket(self, ticket_id: str, fields: Dict[str, Any]) -> bool:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return False

        logger.info(f"Updating ticket {ticket_id} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.update_ticket(ticket_id, fields)
        except Exception as e:
            logger.error(f"Failed to update ticket: {e}")
            return False

    async def add_comment(self, ticket_id: str, comment: str) -> bool:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return False

        logger.info(f"Adding comment to {ticket_id} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.add_comment(ticket_id, comment)
        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
            return False

    async def close_ticket(self, ticket_id: str, resolution: Optional[str] = None) -> bool:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return False

        logger.info(f"Closing ticket {ticket_id} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.close_ticket(ticket_id, resolution)
        except Exception as e:
            logger.error(f"Failed to close ticket: {e}")
            return False

    async def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return None

        try:
            return await self._default_plugin.get_ticket(ticket_id)
        except Exception as e:
            logger.error(f"Failed to get ticket: {e}")
            return None


_dispatcher_instance: Optional[TicketingDispatcher] = None


def get_ticketing_dispatcher(plugin_manager: Optional[PluginManager] = None) -> TicketingDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize TicketingDispatcher")
        _dispatcher_instance = TicketingDispatcher(plugin_manager)

    return _dispatcher_instance


async def create_ticket(
    summary: str, description: str, assignee: Optional[str] = None, labels: Optional[list] = None, **kwargs
) -> Optional[str]:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.create_ticket(summary, description, assignee, labels, **kwargs)


async def add_comment(ticket_id: str, comment: str) -> bool:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.add_comment(ticket_id, comment)


async def close_ticket(ticket_id: str, resolution: Optional[str] = None) -> bool:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.close_ticket(ticket_id, resolution)
