"""
Dispatchers - Generic dispatch layer for plugin operations

Two types of dispatchers:

1. SinglePluginDispatcher: Routes to ONE plugin (hardware, provisioner, etc.)
   - Use when operation should only happen once
   - Example: Don't reboot via multiple hardware plugins simultaneously

2. MultiPluginDispatcher: Routes to ALL enabled plugins (notifiers, etc.)
   - Use when operation should broadcast to all providers
   - Example: Send notification to email + Slack + Google Chat

All dispatchers follow the pattern:
1. Accept a PluginManager instance
2. Automatically discover enabled plugins
3. Route operations to the appropriate plugin(s)
4. Provide convenience functions for common operations
"""

from .base import BaseDispatcher, SinglePluginDispatcher, MultiPluginDispatcher
from .provisioner import ProvisionerDispatcher, get_provisioner_dispatcher
from .switch import SwitchDispatcher, get_switch_dispatcher
from .hardware import HardwareDispatcher, get_hardware_dispatcher
from .chat import ChatDispatcher, get_chat_dispatcher
from .ticketing import TicketingDispatcher, get_ticketing_dispatcher
from .cloud import CloudDispatcher, get_cloud_dispatcher
from .release import ReleaseDispatcher, get_release_dispatcher

__all__ = [
    "BaseDispatcher",
    "SinglePluginDispatcher",
    "MultiPluginDispatcher",
    "ProvisionerDispatcher",
    "SwitchDispatcher",
    "HardwareDispatcher",
    "ChatDispatcher",
    "TicketingDispatcher",
    "CloudDispatcher",
    "ReleaseDispatcher",
    "get_provisioner_dispatcher",
    "get_switch_dispatcher",
    "get_hardware_dispatcher",
    "get_chat_dispatcher",
    "get_ticketing_dispatcher",
    "get_cloud_dispatcher",
    "get_release_dispatcher",
]
