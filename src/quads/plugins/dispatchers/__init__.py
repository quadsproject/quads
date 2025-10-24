"""
Dispatchers - Generic dispatch layer for plugin operations

All dispatchers follow the same pattern:
1. Accept a PluginManager instance
2. Automatically discover enabled plugins
3. Route operations to the appropriate plugin
4. Provide convenience functions for common operations
"""

from .base import BaseDispatcher
from .provisioner import ProvisionerDispatcher, get_provisioner_dispatcher
from .switch import SwitchDispatcher, get_switch_dispatcher
from .hardware import HardwareDispatcher, get_hardware_dispatcher
from .notifier import NotificationDispatcher, get_notification_dispatcher
from .ticketing import TicketingDispatcher, get_ticketing_dispatcher
from .cloud import CloudDispatcher, get_cloud_dispatcher
from .migration import MigrationDispatcher, get_migration_dispatcher

__all__ = [
    "BaseDispatcher",
    "ProvisionerDispatcher",
    "SwitchDispatcher",
    "HardwareDispatcher",
    "NotificationDispatcher",
    "TicketingDispatcher",
    "CloudDispatcher",
    "MigrationDispatcher",
    "get_provisioner_dispatcher",
    "get_switch_dispatcher",
    "get_hardware_dispatcher",
    "get_notification_dispatcher",
    "get_ticketing_dispatcher",
    "get_cloud_dispatcher",
    "get_migration_dispatcher",
]
