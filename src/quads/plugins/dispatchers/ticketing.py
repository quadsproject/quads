#!/usr/bin/env python3
"""
Ticketing Dispatcher - Automatically routes to enabled ticketing system

Uses SinglePluginDispatcher because tickets should be created in ONE
ticketing system at a time (you typically don't create the same ticket
in both JIRA and ServiceNow simultaneously).
"""
import logging
from typing import Optional, Dict, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class TicketingDispatcher(SinglePluginDispatcher[TicketingPlugin]):
    """
    Dispatches ticketing operations to the enabled ticketing plugin.

    Core code calls generic methods without knowing if it's
    JIRA, ServiceNow, GitHub Issues, etc.

    This is a SinglePluginDispatcher - only ONE ticketing system is used at a time.
    """

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, TicketingPlugin, "Ticketing")

    async def create_ticket(
        self, summary: str, description: str, assignee: Optional[str] = None, labels: Optional[list] = None, **kwargs
    ) -> Optional[str]:
        """
        Create a ticket in the ticketing system.

        Returns: Ticket ID/key (e.g., "CLOUD-1234")
        """
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
        """Update an existing ticket"""
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
        """Add a comment to a ticket"""
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
        """Close a ticket"""
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
        """Get ticket details"""
        if not self._default_plugin:
            logger.error("No ticketing plugin enabled")
            return None

        try:
            return await self._default_plugin.get_ticket(ticket_id)
        except Exception as e:
            logger.error(f"Failed to get ticket: {e}")
            return None


# Singleton instance
_dispatcher_instance: Optional[TicketingDispatcher] = None


def get_ticketing_dispatcher(plugin_manager: Optional[PluginManager] = None) -> TicketingDispatcher:
    """Get the global TicketingDispatcher instance"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize TicketingDispatcher")
        _dispatcher_instance = TicketingDispatcher(plugin_manager)

    return _dispatcher_instance


# Convenience functions
async def create_ticket(
    summary: str, description: str, assignee: Optional[str] = None, labels: Optional[list] = None, **kwargs
) -> Optional[str]:
    """
    Create a ticket in the configured ticketing system.

    Example:
        from quads.plugins.ticketing_dispatcher import create_ticket

        # Works with JIRA, ServiceNow, GitHub, etc. - whatever is enabled!
        ticket_id = await create_ticket(
            summary="New cloud assignment",
            description="User requested cloud05 for testing",
            assignee="jdoe",
            labels=["cloud", "assignment"]
        )
        # Returns: "CLOUD-1234" (or equivalent for other systems)
    """
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.create_ticket(summary, description, assignee, labels, **kwargs)


async def add_comment(ticket_id: str, comment: str) -> bool:
    """Add comment to ticket"""
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.add_comment(ticket_id, comment)


async def close_ticket(ticket_id: str, resolution: Optional[str] = None) -> bool:
    """Close a ticket"""
    dispatcher = get_ticketing_dispatcher()
    return await dispatcher.close_ticket(ticket_id, resolution)
