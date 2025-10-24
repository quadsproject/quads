from src.quads.plugins.interfaces.ticketing import TicketingPlugin
from src.quads.config import Config
from src.quads.tools.external.jira import Jira


class JiraTicketingPlugin(TicketingPlugin):
    """Jira ticketing plugin"""

    def __init__(self):
        self.url = Config.jira_url
        self.username = Config.jira_username
        self.password = Config.jira_password
        self.token = Config.jira_token

    def create_ticket(self, title: str, description: str) -> bool:
        """Create a ticket"""
        jira = Jira(self.url, self.username, self.password, self.token)
        return jira.create_ticket(title, description)
