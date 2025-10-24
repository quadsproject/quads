from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List
from quads.server.models import Assignment


class ValidatorPlugin(BasePlugin):
    """Interface for validator plugins"""

    @abstractmethod
    async def validate(
        self,
        cloud: str,
        assignment: Assignment,
        hosts: List,
        skip_system: bool,
        skip_network: bool,
        report: str = "",
    ) -> tuple[bool, str]:
        """
        Validate an environment.

        Args:
            cloud: Cloud name to validate
            assignment: The assignment object
            hosts: List of hosts to validate
            skip_system: Whether to skip system validation
            skip_network: Whether to skip network validation
            report: Initial report string

        Returns:
            Tuple of (validation_success, report_string)
        """
        pass
