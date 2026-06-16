import logging
from typing import Optional, Dict, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.plugins.manager import PluginManager, get_plugin_manager

logger = logging.getLogger(__name__)


class TicketingDispatcher(SinglePluginDispatcher[TicketingPlugin]):
    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, TicketingPlugin, "Ticketing")

    async def create_ticket(
        self, summary: str, description: str, labels: Optional[list] = None, **kwargs
    ) -> Optional[str]:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return None

        logger.info(f"Creating ticket via {self._default_plugin.name}: {summary}")
        try:
            return await self._default_plugin.create_ticket(summary, description, labels, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create ticket: {e}")
            return None

    async def post_comment(self, ticket_id: str, comment: str) -> bool:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return False

        logger.info(f"Adding comment to {ticket_id} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.post_comment(ticket_id, comment)
        except Exception as e:
            logger.error(f"Failed to add comment: {e}")
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

    async def get_transitions(self, ticket_id: str) -> list:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return []

        try:
            return await self._default_plugin.get_transitions(ticket_id)
        except Exception as e:
            logger.error(f"Failed to get transitions: {e}")
            return []

    async def post_transition(self, ticket_id: str, transition_id: str) -> bool:
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return False

        logger.info(f"Transitioning {ticket_id} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.post_transition(ticket_id, transition_id)
        except Exception as e:
            logger.error(f"Failed to post transition: {e}")
            return False


_dispatcher_instance: Optional[TicketingDispatcher] = None


def get_ticketing_dispatcher(plugin_manager: Optional[PluginManager] = None) -> TicketingDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            plugin_manager = get_plugin_manager()
        _dispatcher_instance = TicketingDispatcher(plugin_manager)

    return _dispatcher_instance


async def create_ticket(summary: str, description: str, labels: Optional[list] = None, **kwargs) -> Optional[str]:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.create_ticket(summary, description, labels, **kwargs)


async def post_comment(ticket_id: str, comment: str) -> bool:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.post_comment(ticket_id, comment)


async def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.get_ticket(ticket_id)


async def get_transitions(ticket_id: str) -> list:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.get_transitions(ticket_id)


async def post_transition(ticket_id: str, transition_id: str) -> bool:
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.post_transition(ticket_id, transition_id)
