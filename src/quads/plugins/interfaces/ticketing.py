from src.quads.plugins.base import BasePlugin
from abc import abstractmethod


class TicketingPlugin(BasePlugin):
    """Interface for ticketing plugins"""

    @abstractmethod
    def create_ticket(self, title: str, description: str) -> bool:
        """Create a ticket"""
        pass

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> dict:
        """Get a ticket"""
        pass
