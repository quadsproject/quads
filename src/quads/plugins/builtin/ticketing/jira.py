from src.quads.plugins.interfaces.ticketing import TicketingPlugin
from src.quads.config import Config
from src.quads.tools.external.jira import Jira, JiraException


class JiraTicketingPlugin(TicketingPlugin):
    """Jira ticketing plugin"""

    def __init__(self):
        self.url = Config.jira_url
        self.username = Config.jira_username
        self.password = Config.jira_password
        self.token = Config.jira_token

    def create_ticket(self, summary: str, description: str, labels: list = None) -> str:
        """Create a ticket"""
        jira = Jira(self.url, self.username, self.password, self.token)
        response = jira.create_ticket(summary, description, labels)
        if response:
            return response.get("key").split("-")[1]
        else:
            raise JiraException(f"Failed to create ticket: {response}")

    def post_comment(self, ticket_id: str, comment: str) -> bool:
        """Post a comment to a ticket"""
        jira = Jira(self.url, self.username, self.password, self.token)
        return jira.post_comment(ticket_id, comment)

    def get_ticket(self, ticket_id: str) -> dict:
        """Get a ticket"""
        jira = Jira(self.url, self.username, self.password, self.token)
        return jira.get_ticket(ticket_id)
