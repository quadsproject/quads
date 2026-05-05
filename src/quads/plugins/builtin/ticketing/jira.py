from typing import Optional
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.tools.external.jira import Jira, JiraException
from quads.plugins.manager import PluginManager


class JiraTicketingPlugin(TicketingPlugin):
    """
    Jira ticketing plugin implementing TicketingPlugin interface.

    Manages ticket creation, retrieval, and management.
    """

    name = "jira"
    version = "1.0.0"
    description = "Jira ticketing plugin"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.url = self.config.get("url")
        self.username = self.config.get("username")
        self.password = self.config.get("password")
        self.token = self.config.get("token")
        self.ticket_queue = self.config.get("ticket_queue")
        self.auth_type = self.config.get("auth_type", "basic")
        self.jira = Jira(self.url, self.username, self.password, self.token, self.ticket_queue, self.auth_type)
        return True

    async def create_ticket(self, summary: str, description: str, labels: list = None) -> str:
        """Create a ticket"""
        response = await self.jira.create_ticket(summary, description, labels)
        if response:
            return response.get("key").split("-")[1]
        else:
            raise JiraException(f"Failed to create ticket: {response}")

    async def post_comment(self, ticket_id: str, comment: str) -> bool:
        """Post a comment to a ticket"""
        return await self.jira.post_comment(ticket_id, comment)

    async def get_ticket(self, ticket_id: str) -> dict:
        """Get a ticket"""
        return await self.jira.get_ticket(ticket_id)
