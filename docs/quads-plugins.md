# QUADS Plugin Architecture

QUADS now features a flexible, extensible plugin architecture that allows you to integrate with various external systems and extend functionality without modifying core code.

## Table of Contents

- [Overview](#overview)
- [Plugin Types](#plugin-types)
- [Configuration](#configuration)
- [Built-in Plugins](#built-in-plugins)
- [Creating Custom Plugins](#creating-custom-plugins)
- [Plugin Discovery](#plugin-discovery)
- [Migration from Legacy Systems](#migration-from-legacy-systems)

## Overview

The plugin architecture provides:

- **Modularity**: Cleanly separated concerns with well-defined interfaces
- **Extensibility**: Add new integrations without modifying core QUADS code
- **Flexibility**: Enable/disable plugins via configuration
- **Type Safety**: Strongly typed plugin interfaces for each category
- **Discovery**: Automatic plugin discovery from built-in and external locations

Plugins are configured in `/opt/quads/conf/plugins.yml` and automatically discovered and loaded at startup.

## Plugin Types

QUADS supports the following plugin categories:

### Chat Plugins

Send notifications to chat/messaging platforms.

**Interface**: `ChatPlugin`
**Methods**: `send_message(message, channels=None, **kwargs)` (async)

**Built-in Plugins**:
- `slack` - Slack webhook integration
- `gchat` - Google Chat integration
- `irc` - IRC channel notifications

### Dayzero Plugins

Post-release plugins that run on the first host of a new cloud assignment after it is released.

**Interface**: `DayzeroPlugin`
**Methods**: `execute(cloud)` (async)

**Built-in Plugins**:
- `cloudcmd` - runs the owner's release command on the first host via tmux
- `clouddata` - drops `/root/quads_env.yml` metadata on the first host

### Email Plugins

Send email notifications for assignments and system events.

**Interface**: `EmailPlugin`
**Methods**: `send_mail(subject, content, recipients, cc=None, **kwargs)` (async)

**Built-in Plugins**:
- `email` - SMTP email delivery

### Hardware Plugins

Manage bare metal hardware via IPMI/Redfish.

**Interface**: `HardwarePlugin`
**Methods**:
- `init(host, rack, uloc, blade)`
- `change_boot(boot_order, interfaces_path)`
- `set_power_state(state)`
- `reboot_server(graceful=False)`
- `get_power_state()`
- `get_vendor()`
- `boot_to_type(host_type, interfaces_path)`
- `set_next_boot_pxe()`
- `unmount_virtual_media()`
- `detach_remote_image()`
- `get_bios_attribute(attribute)`

**Built-in Plugins**:
- `badfish` - Badfish IPMI/Redfish automation

### Provisioner Plugins

Integrate with provisioning backends.

**Interface**: `ProvisionerPlugin`
**Methods**:
- `prepare_host_provisioning(host_name, cloud, os_type)`
- `get_all_hosts()`
- `get_images()`

**Built-in Plugins**:
- `foreman` - Foreman/Satellite provisioning

### Release Plugins

Manage environment release and handoff processes.

**Interface**: `ReleasePlugin`
**Methods**: `move_and_rebuild(host, new_cloud, semaphore, rebuild=False, schedule_id=None)`

**Built-in Plugins**:
- `standard` - Standard QUADS release workflow

### Switch Plugins

Automate network switch VLAN configurations.

**Interface**: `SwitchPlugin`
**Methods**:
- `configure(host, old_cloud, new_cloud)`
- `modify(host, change=False, overrides=None)`
- `verify(host=None, cloud=None, change=False)`
- `ls_config(cloud, all=False)`

**Built-in Plugins**:
- `juniper` - Juniper switch automation (Q-in-Q VLANs)

### Ticketing Plugins

Integrate with ticketing/issue tracking systems.

**Interface**: `TicketingPlugin`
**Methods**:
- `create_ticket(summary, description, labels=None)`
- `post_comment(ticket_id, comment)`
- `get_ticket(ticket_id)`
- `get_transitions(ticket_id)`
- `post_transition(ticket_id, transition_id)`

**Built-in Plugins**:
- `jira` - Atlassian JIRA integration

### Validator Plugins

Validate environment health and connectivity.

**Interface**: `ValidatorPlugin`
**Methods**: `validate(cloud, assignment, hosts, skip_system, skip_network, report)`

**Built-in Plugins**:
- `environment` - Comprehensive environment validation (replaces `validate_env.py`)

## Configuration

Plugins are configured in `/opt/quads/conf/plugins.yml`:

```yaml
plugins:
  # Chat notifications
  slack:
    enabled: true
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
    default_channel: "#quads"
    username: "QUADS Bot"
    icon_emoji: ":robot_face:"

  gchat:
    enabled: false
    webhook_url: https://chat.googleapis.com/v1/spaces/SPACE_ID/messages?key=KEY

  irc:
    enabled: false
    server: irc.libera.chat
    port: 6667
    default_channel: "#quads"

  # Email
  email:
    enabled: true
    mail_display_name: QUADS Scheduler
    smtp_host: mail.example.com
    smtp_port: 25
    from_address: quads@example.com
    reply_to: dev-null@example.com
    user_agent: QUADS Notifier
    report_cc: user1@example.com, user2@example.com

  # Hardware management
  badfish:
    enabled: true
    ipmi_username: root
    ipmi_password: ${IPMI_PASSWORD}
    # Comma-separated model/name fragments for Supermicro hosts that should
    # skip Badfish and use the raw ipmitool path instead.
    # skip_for_supermicro_models: 6029p, 1028r, 1029u

  # Provisioning
  foreman:
    enabled: true
    url: https://foreman.example.com/hosts/
    api_url: https://foreman.example.com/api/v2
    username: admin
    password: ${FOREMAN_PASSWORD}
    token: ${FOREMAN_TOKEN}
    default_os: "RHEL 9"
    default_boot_order: "foreman"
    rbac_exclude: ""  # Exclude clouds from Foreman automation
    rbac_user_mail: ""  # Email used when creating new QUADS cloud users in Foreman
    rbac_auth_source_id: 1  # Foreman auth-source ID for new cloud users

  # Release management
  standard:
    enabled: true
    # Number of retry attempts for IPMI credential set + verify
    ipmi_credential_retries: 3
    # Delay in seconds between retry attempts (per-host, runs in parallel)
    ipmi_credential_retry_delay: 10

  # Switch automation
  juniper:
    enabled: true
    username: scaleadmin
    # Password configured via host metadata or environment

  # Ticketing
  jira:
    enabled: true
    auth_type: basic  # or 'token'
    url: https://jira.example.com/rest/api/2
    username: ${JIRA_USERNAME}
    password: ${JIRA_PASSWORD}
    token: ${JIRA_TOKEN}
    ticket_queue: SCALELAB

  # Validation
  environment:
    enabled: true
```

### Placeholder Values

Values shown as `${VAR_NAME}`, for example `${FOREMAN_PASSWORD}` or `${JIRA_USERNAME}`,
are placeholders from the shipped `plugins.yml` and must be replaced with real values.
QUADS does not perform environment variable substitution, these strings are used literally.

### Enabling/Disabling Plugins

Each plugin can be enabled or disabled via the `enabled` flag:

```yaml
slack:
  enabled: true  # Plugin will load

gchat:
  enabled: false  # Plugin will not load
```

## Built-in Plugins

### Slack Plugin

Send notifications to Slack channels via webhooks.

```yaml
slack:
  enabled: true
  webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
  default_channel: "#quads"
  username: "QUADS Bot"
  icon_emoji: ":robot_face:"
```

**Usage**: Automatically sends notifications for assignment events, system alerts, and environment releases.

### Google Chat Plugin

Send notifications to Google Chat spaces.

```yaml
gchat:
  enabled: true
  webhook_url: https://chat.googleapis.com/v1/spaces/SPACE_ID/messages?key=KEY
```

### IRC Plugin

Send notifications to IRC channels.

```yaml
irc:
  enabled: true
  server: irc.libera.chat
  port: 6667
  default_channel: "#quads"
```

### Email Plugin

Send email notifications via SMTP.

```yaml
email:
  enabled: true
  mail_display_name: QUADS Scheduler
  smtp_host: mail.example.com
  smtp_port: 25
  from_address: quads@example.com
  reply_to: dev-null@example.com
  user_agent: QUADS Notifier
  report_cc: admin1@example.com, admin2@example.com
```

**Features**:
- Assignment confirmation emails
- Environment ready notifications
- Expiration reminders
- System alerts

### Badfish Plugin

IPMI/Redfish hardware management via Badfish.

```yaml
badfish:
  enabled: true
  ipmi_username: root
  ipmi_password: ${IPMI_PASSWORD}
  # Comma-separated model/name fragments for Supermicro hosts that should
  # skip Badfish and use the raw ipmitool path instead.
  # skip_for_supermicro_models: 6029p, 1028r, 1029u
```

**Features**:
- Power management (on/off/cycle, reboot)
- Boot order configuration
- Hardware health monitoring

### Foreman Plugin

Foreman/Satellite provisioning integration.

```yaml
foreman:
  enabled: true
  url: https://foreman.example.com/hosts/
  api_url: https://foreman.example.com/api/v2
  username: admin
  password: ${FOREMAN_PASSWORD}
  token: ${FOREMAN_TOKEN}
  default_os: "RHEL 9"
  default_boot_order: "foreman"
  rbac_exclude: "cloud32|cloud04"  # Exclude specific clouds
  rbac_user_mail: ""  # Email used when creating new QUADS cloud users in Foreman
  rbac_auth_source_id: 1  # Foreman auth-source ID for new cloud users
```

**Features**:
- OS provisioning and rebuild
- Automatic Foreman RBAC bootstrap via `foreman_setup.py`
- Cloud user creation and management

### Standard Release Plugin

Standard environment release workflow.

```yaml
standard:
  enabled: true
  ipmi_credential_retries: 3
  ipmi_credential_retry_delay: 10
```

**Workflow**:
1. Pre-release validation
2. Notification to tenant
3. Environment handoff
4. Post-release verification

### Juniper Plugin

Juniper switch VLAN automation.

```yaml
juniper:
  enabled: true
  username: scaleadmin
  # Password from host metadata or JUNIPER_PASSWORD env var
```

**Features**:
- Q-in-Q VLAN configuration
- VLAN verification
- Automatic rollback on failure

### JIRA Plugin

Atlassian JIRA integration for ticketing.

```yaml
jira:
  enabled: true
  auth_type: basic  # or 'token'
  url: https://jira.example.com/rest/api/2
  username: ${JIRA_USERNAME}
  password: ${JIRA_PASSWORD}
  token: ${JIRA_TOKEN}
  ticket_queue: SCALELAB
```

**Features**:
- Automatic ticket creation for assignments
- Comment updates on state changes
- Watcher management
- Automatic ticket closure

### Environment Validator Plugin

Comprehensive environment validation (replaces legacy `validate_env.py`).

```yaml
environment:
  enabled: true
```

**Validation Checks**:
- System connectivity (SSH)
- Network reachability
- VLAN configurations
- Service health
- DNS resolution
- Provisioning state

## Creating Custom Plugins

### Plugin Structure

Create a custom plugin by implementing the appropriate interface:

```python
# /opt/quads/plugins/custom_chat.py
from typing import List, Optional
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.manager import PluginManager

class CustomChatPlugin(ChatPlugin):
    """Custom chat integration"""

    name = "custom_chat"
    version = "1.0.0"
    description = "Custom chat platform integration"
    author = "Your Name"

    def initialize(self, plugin_manager: Optional[PluginManager] = None) -> bool:
        """Initialize plugin"""
        self.api_key = self.config.get("api_key")
        self.workspace = self.config.get("workspace")

        if not self.api_key:
            self.logger.error("api_key not configured")
            return False

        self.logger.info(f"Custom chat plugin initialized")
        return True

    async def send_message(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs
    ) -> bool:
        """Send message to chat platform"""
        try:
            # Your implementation here
            self.logger.info(f"Sent message to {channels}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False
```

### Plugin Configuration

Add configuration to `plugins.yml`:

```yaml
custom_chat:
  enabled: true
  api_key: ${CUSTOM_CHAT_API_KEY}
  workspace: my-workspace
```

### Plugin Location

Place custom plugins in:

1. **External plugins directory**: `/opt/quads/plugins/` (recommended)

Plugins are automatically discovered and loaded on startup.

### Available Interfaces

Import the appropriate base class for your plugin type:

```python
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.interfaces.cloud import CloudPlugin
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.interfaces.email import EmailPlugin
from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.interfaces.release import ReleasePlugin
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.plugins.interfaces.ticketing import TicketingPlugin
from quads.plugins.interfaces.validator import ValidatorPlugin
```

### Plugin Lifecycle

1. **Discovery**: Plugins discovered from built-in and external paths
2. **Configuration**: Plugin settings loaded from `plugins.yml`
3. **Initialization**: Plugin `initialize()` method called
4. **Registration**: Successfully initialized plugins registered with manager
5. **Usage**: QUADS components access plugins via dispatcher interfaces

### Testing Custom Plugins

Test your plugin independently:

```python
from quads.plugins.manager import PluginManager
from quads.config import Config

# Initialize plugin manager
manager = PluginManager(Config)
manager.initialize()

# Get your plugin
chat_plugin = manager.get_plugin("custom_chat")

# Test functionality
await chat_plugin.send_message("Test message", ["#general"])
```

## Plugin Discovery

### Discovery Paths

Plugins are discovered from:

1. **Built-in plugins**: `quads.plugins.builtin.*`
   - `quads.plugins.builtin.chat`
   - `quads.plugins.builtin.cloud`
   - `quads.plugins.builtin.dayzero`
   - `quads.plugins.builtin.email`
   - `quads.plugins.builtin.hardware`
   - `quads.plugins.builtin.provisioners`
   - `quads.plugins.builtin.release`
   - `quads.plugins.builtin.switches`
   - `quads.plugins.builtin.ticketing`
   - `quads.plugins.builtin.validators`

2. **External plugins**: `/opt/quads/plugins/`

### Discovery Process

1. Scan all discovery paths for Python modules
2. Import each module
3. Find classes inheriting from `BasePlugin`
4. Register by plugin `name` attribute (for modules inside a builtin package the `name` must also match the module filename)
5. Load enabled plugins from configuration

### Plugin Manager

Access plugins via the `PluginManager`:

```python
from quads.plugins.manager import PluginManager

manager = PluginManager()
manager.initialize()

# Get specific plugin
slack = manager.get_plugin("slack")

# Get all chat plugins
chat_plugins = manager.get_plugins_by_type(ChatPlugin)
```

## Migration from Legacy Systems

The plugin architecture replaces several legacy tools:

### Removed Legacy Tools

| Legacy Tool | Replacement Plugin | Migration Notes |
|------------|-------------------|-----------------|
| `move_and_rebuild.py` | `standard` release plugin | Integrated into release workflow |
| `validate_env.py` | `environment` validator plugin | Same validation logic, plugin interface |
| `tools/external/postman.py` | `email` plugin | Configurable via plugins.yml |
| Hardcoded switch logic | `juniper` plugin | Extensible for other switch vendors |
| Hardcoded Foreman calls | `foreman` plugin | Cleaner interface, easier testing |

### Configuration Migration

**Old** (`quads.yml`):
```yaml
# Email settings mixed with other config
smtp_host: mail.example.com
from_address: quads@example.com

# Foreman settings mixed with other config
foreman_url: https://foreman.example.com
foreman_username: admin
```

**New** (`plugins.yml`):
```yaml
# Cleanly separated plugin configurations
email:
  enabled: true
  smtp_host: mail.example.com
  from_address: quads@example.com

foreman:
  enabled: true
  url: https://foreman.example.com
  username: admin
```

### Code Migration

**Old approach** (direct imports):
```python
from quads.tools.external.foreman import Foreman
from quads.tools.validate_env import validate_env

# Tightly coupled to implementation
foreman = Foreman(config)
foreman.build_host(hostname)
```

**New approach** (plugin-based):
```python
from quads.plugins.manager import PluginManager

# Loosely coupled, swappable implementations
manager = PluginManager()
provisioner = manager.get_plugin("foreman")
await provisioner.prepare_host_provisioning("host01.example.com", "cloud04", "RHEL 9")
```

### Benefits of Plugin Architecture

1. **Modularity**: Clear separation of concerns
2. **Testability**: Mock plugins for unit tests
3. **Extensibility**: Add integrations without modifying core
4. **Flexibility**: Enable/disable features via configuration
5. **Maintainability**: Isolated, well-defined interfaces

## See Also

- [QUADS API Documentation](quads-api.md)
- [QUADS Workflow](quads-workflow.md)
- [Switch and Host Setup](switch-host-setup.md)
- [Using JIRA with QUADS](using-jira-with-quads.md)
