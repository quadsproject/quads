from src.quads.plugins.base import BasePlugin
from abc import abstractmethod


class TicketingPlugin(BasePlugin):
    """Interface for ticketing plugins"""

    @abstractmethod
    def create_ticket(self, summary: str, description: str, labels: list = None) -> str:
        """Create a ticket"""
        pass

    @abstractmethod
    def post_comment(self, ticket_id: str, comment: str) -> bool:
        """Post a comment to a ticket"""
        pass

    @abstractmethod
    def get_ticket(self, ticket_id: str) -> dict:
        """Get a ticket"""
        pass
