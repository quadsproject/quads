from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Optional, List


class ValidatorPlugin(BasePlugin):
    """Interface for validator plugins"""

    @abstractmethod
    async def validate_env(
        self,
        cloud: str,
        assignment,
        hosts: List,
        args,
        report: str = "",
    ) -> tuple[bool, str]:
        """
        Validate an environment.

        Args:
            cloud: Cloud name to validate
            assignment: The assignment object
            hosts: List of hosts to validate
            args: Arguments/configuration for validation
            report: Initial report string

        Returns:
            Tuple of (validation_success, report_string)
        """
        pass

    @abstractmethod
    async def notify_failure(
        self,
        cloud: str,
        owner: str,
        ticket: str,
        report: str,
    ) -> None:
        """
        Send failure notification.

        Args:
            cloud: Cloud name
            owner: Assignment owner
            ticket: Ticket identifier
            report: Validation report
        """
        pass

    @abstractmethod
    async def notify_success(
        self,
        cloud: str,
        owner: str,
        ticket: str,
    ) -> None:
        """
        Send success notification.

        Args:
            cloud: Cloud name
            owner: Assignment owner
            ticket: Ticket identifier
        """
        pass
