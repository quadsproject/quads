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

    async def validate(
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
            return await plugin.validate(cloud, assignment, hosts, args, report)
        except Exception as e:
            logger.error(f"Failed to validate environment: {e}", exc_info=True)
            return False, report + f"\nValidation error: {str(e)}\n"


_dispatcher_instance: Optional[ValidatorDispatcher] = None


def get_validator_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ValidatorDispatcher:
    """Get or create the validator dispatcher singleton"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ValidatorDispatcher")
        _dispatcher_instance = ValidatorDispatcher(plugin_manager)

    return _dispatcher_instance


async def validate(cloud: str, assignment, hosts: List, args, report: str = "") -> Tuple[bool, str]:
    dispatcher = get_validator_dispatcher()
    return await dispatcher.validate(cloud, assignment, hosts, args, report)
