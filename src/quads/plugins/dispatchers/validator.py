import logging
from typing import Optional, List, Tuple
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.validator import ValidatorPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ValidatorDispatcher(SinglePluginDispatcher[ValidatorPlugin]):
    """Dispatcher for validator plugins"""

    def __init__(self, plugin_manager: PluginManager, plugin_name: Optional[str] = None):
        super().__init__(plugin_manager, ValidatorPlugin, "Validator", plugin_name=plugin_name)

    async def validate_env(
        self,
        cloud: str,
        assignment,
        hosts: List,
        args,
        report: str = "",
    ) -> Tuple[bool, str]:
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
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return False, report

        try:
            logger.info(f"Validating environment {cloud} via {plugin.name}")
            return await plugin.validate_env(cloud, assignment, hosts, args, report)
        except Exception as e:
            logger.error(f"Failed to validate environment: {e}", exc_info=True)
            return False, report + f"\nValidation error: {str(e)}\n"

    async def post_system_test(
        self,
        cloud: str,
        assignment,
        hosts: List,
        report: str = "",
    ) -> Tuple[bool, str]:
        """
        Run post-system validation tests.

        Args:
            cloud: Cloud name
            assignment: The assignment object
            hosts: List of hosts to test
            report: Current report string

        Returns:
            Tuple of (test_success, report_string)
        """
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return False, report

        try:
            logger.info(f"Running system tests for {cloud} via {plugin.name}")
            return await plugin.post_system_test(cloud, assignment, hosts, report)
        except Exception as e:
            logger.error(f"Failed to run system tests: {e}", exc_info=True)
            return False, report + f"\nSystem test error: {str(e)}\n"

    async def post_network_test(
        self,
        cloud: str,
        assignment,
        hosts: List,
        report: str = "",
    ) -> Tuple[bool, str]:
        """
        Run post-network validation tests.

        Args:
            cloud: Cloud name
            assignment: The assignment object
            hosts: List of hosts to test
            report: Current report string

        Returns:
            Tuple of (test_success, report_string)
        """
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return False, report

        try:
            logger.info(f"Running network tests for {cloud} via {plugin.name}")
            return await plugin.post_network_test(cloud, assignment, hosts, report)
        except Exception as e:
            logger.error(f"Failed to run network tests: {e}", exc_info=True)
            return False, report + f"\nNetwork test error: {str(e)}\n"

    async def env_allocation_time_exceeded(self, cloud: str) -> bool:
        """
        Check if the environment allocation time has exceeded the grace period.

        Args:
            cloud: Cloud name to check

        Returns:
            True if time exceeded, False otherwise
        """
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return False

        try:
            return await plugin.env_allocation_time_exceeded(cloud)
        except Exception as e:
            logger.error(f"Failed to check allocation time: {e}", exc_info=True)
            return False

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
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return

        try:
            logger.info(f"Sending failure notification for {cloud} via {plugin.name}")
            await plugin.notify_failure(cloud, owner, ticket, report)
        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}", exc_info=True)

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
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No validator plugin enabled")
            return

        try:
            logger.info(f"Sending success notification for {cloud} via {plugin.name}")
            await plugin.notify_success(cloud, owner, ticket)
        except Exception as e:
            logger.error(f"Failed to send success notification: {e}", exc_info=True)


_dispatcher_instance: Optional[ValidatorDispatcher] = None


def get_validator_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ValidatorDispatcher:
    """Get or create the validator dispatcher singleton"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ValidatorDispatcher")
        _dispatcher_instance = ValidatorDispatcher(plugin_manager)

    return _dispatcher_instance
