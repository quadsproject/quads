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
**Methods**: `send_message(message, channels, **kwargs)`

**Built-in Plugins**:
- `slack` - Slack webhook integration
- `gchat` - Google Chat integration
- `irc` - IRC channel notifications

### Email Plugins

Send email notifications for assignments and system events.

**Interface**: `EmailPlugin`
**Methods**: `send_email(recipients, subject, body, **kwargs)`

**Built-in Plugins**:
- `email` - SMTP email delivery

### Hardware Plugins

Manage bare metal hardware via IPMI/Redfish.

**Interface**: `HardwarePlugin`
**Methods**:
- `power_on(host)`
- `power_off(host)`
- `power_cycle(host)`
- `set_boot_order(host, boot_order)`
- `get_power_state(host)`

**Built-in Plugins**:
- `badfish` - Badfish IPMI/Redfish automation

### Provisioner Plugins

Integrate with provisioning backends.

**Interface**: `ProvisionerPlugin`
**Methods**:
- `build_host(host, os_type)`
- `rebuild_host(host)`
- `get_build_status(host)`

**Built-in Plugins**:
- `foreman` - Foreman/Satellite provisioning

### Release Plugins

Manage environment release and handoff processes.

**Interface**: `ReleasePlugin`
**Methods**: `release_environment(cloud, assignment)`

**Built-in Plugins**:
- `standard` - Standard QUADS release workflow

### Switch Plugins

Automate network switch VLAN configurations.

**Interface**: `SwitchPlugin`
**Methods**:
- `set_vlan(host, interface, vlan_id)`
- `get_vlan(host, interface)`
- `verify_vlan(host, interface, expected_vlan)`

**Built-in Plugins**:
- `juniper` - Juniper switch automation (Q-in-Q VLANs)

### Ticketing Plugins

Integrate with ticketing/issue tracking systems.

**Interface**: `TicketingPlugin`
**Methods**:
- `create_ticket(summary, description, **kwargs)`
- `update_ticket(ticket_id, **kwargs)`
- `add_comment(ticket_id, comment)`
- `close_ticket(ticket_id)`

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
    ssl: false
    default_channel: "#quads"

  # Cloud providers
  aws_cloud:
    enabled: false
    region: us-east-1
    access_key: ${AWS_ACCESS_KEY_ID}  # Environment variable
    secret_key: ${AWS_SECRET_ACCESS_KEY}
    default_ami: ami-0c55b159cbfafe1f0
    subnet_id: subnet-xxxxx
    security_group_ids:
      - sg-xxxxx
    key_name: quads-cloud-key
    max_instances: 50

  ibm_cloud:
    enabled: false
    api_key: ${IBM_CLOUD_API_KEY}
    region: us-south
    vpc_id: r006-xxxxx
    subnet_id: 0717-xxxxx
    resource_group_id: xxxxx
    ssh_key_id: r006-xxxxx
    default_image_id: r006-xxxxx
    default_profile: cx2-2x4
    max_instances: 50

  # Email
  email:
    enabled: true
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

  # Provisioning
  foreman:
    enabled: true
    url: https://foreman.example.com/hosts/
    api_url: https://foreman.example.com/api/v2
    username: admin
    password: ${FOREMAN_PASSWORD}
    token: ${FOREMAN_TOKEN}
    default_os: "RHEL 9"
    default_ptable: "generic-rhel9"
    default_medium: "RHEL Local"
    default_boot_order: "foreman"
    rbac_exclude: ""  # Exclude clouds from Foreman automation

  # Release management
  standard:
    enabled: true

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

### Environment Variable Substitution

Configuration values can reference environment variables using `${VAR_NAME}` syntax:

```yaml
foreman:
  password: ${FOREMAN_PASSWORD}  # Reads from environment
  token: ${FOREMAN_TOKEN}
```

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
  ssl: true
  default_channel: "#quads"
  nickname: "quads-bot"
```

### Email Plugin

Send email notifications via SMTP.

```yaml
email:
  enabled: true
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
```

**Features**:
- Power management (on/off/cycle)
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
  default_ptable: "generic-rhel9"
  default_medium: "RHEL Local"
  default_boot_order: "foreman"
  rbac_exclude: "cloud32|cloud04"  # Exclude specific clouds
```

### Standard Release Plugin

Standard environment release workflow.

```yaml
standard:
  enabled: true
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

Place custom plugins in one of these locations:

1. **External plugins directory**: `/opt/quads/plugins/` (recommended)
2. **Source tree**: `src/quads/plugins/external/`

Plugins are automatically discovered and loaded on startup.

### Available Interfaces

Import the appropriate base class for your plugin type:

```python
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.interfaces.cloud import CloudPlugin
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
4. Register by plugin `name` attribute
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
await provisioner.build_host(hostname)
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
