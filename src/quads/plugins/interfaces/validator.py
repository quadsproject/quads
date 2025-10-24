from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List


class ValidatorPlugin(BasePlugin):
    """Interface for validator plugins"""

    @abstractmethod
    async def validate(
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
