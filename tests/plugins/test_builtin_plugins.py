"""Tests for built-in plugins"""

from unittest.mock import patch

from quads.plugins.builtin.chat.slack import SlackPlugin
from quads.plugins.builtin.chat.gchat import GoogleChatPlugin
from quads.plugins.builtin.chat.irc import IRCPlugin
from quads.plugins.builtin.email.email import EmailPlugin as SMTPEmailPlugin
from quads.plugins.builtin.hardware.badfish import BadfishHardwarePlugin
from quads.plugins.builtin.provisioners.foreman import ForemanProvisionerPlugin
from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin
from quads.plugins.builtin.ticketing.jira import JiraTicketingPlugin


class TestSlackPlugin:
    """Test cases for Slack chat plugin"""

    def test_slack_plugin_metadata(self):
        """Test Slack plugin has correct metadata"""
        assert SlackPlugin.name == "slack"
        assert SlackPlugin.version == "1.0.0"
        assert SlackPlugin.description == "Send notifications to Slack channels via webhooks"
        assert SlackPlugin.author == "QUADS Team"

    def test_slack_plugin_initialization_success(self):
        """Test Slack plugin initializes with valid config"""
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.slack.com/services/XXX",
            "default_channel": "#test",
        }
        plugin = SlackPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.webhook_url == config["webhook_url"]
        assert plugin.default_channel == "#test"

    def test_slack_plugin_initialization_missing_webhook(self, caplog):
        """Test Slack plugin fails without webhook_url"""
        config = {"enabled": True}
        plugin = SlackPlugin(config)
        result = plugin.initialize()

        assert result is False
        assert "webhook_url not configured" in caplog.text

    def test_slack_plugin_config_parameters(self):
        """Test Slack plugin stores config parameters correctly"""
        config = {
            "enabled": True,
            "webhook_url": "https://hooks.slack.com/services/XXX",
            "default_channel": "#custom",
            "username": "Custom Bot",
        }
        plugin = SlackPlugin(config)
        plugin.initialize()

        assert plugin.webhook_url == "https://hooks.slack.com/services/XXX"
        assert plugin.default_channel == "#custom"
        assert plugin.username == "Custom Bot"


class TestGChatPlugin:
    """Test cases for Google Chat plugin"""

    def test_gchat_plugin_metadata(self):
        """Test GChat plugin has correct metadata"""
        assert GoogleChatPlugin.name == "gchat"
        assert GoogleChatPlugin.version == "1.0.0"

    def test_gchat_plugin_initialization_success(self):
        """Test GChat plugin initializes with valid config"""
        config = {
            "enabled": True,
            "webhook_url": "https://chat.googleapis.com/v1/spaces/XXX",
        }
        plugin = GoogleChatPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.webhook_url == config["webhook_url"]

    def test_gchat_plugin_initialization_missing_webhook(self, caplog):
        """Test GChat plugin fails without webhook_url"""
        config = {"enabled": True}
        plugin = GoogleChatPlugin(config)
        result = plugin.initialize()

        assert result is False
        assert "webhook_url not configured" in caplog.text


class TestIRCPlugin:
    """Test cases for IRC plugin"""

    def test_irc_plugin_metadata(self):
        """Test IRC plugin has correct metadata"""
        assert IRCPlugin.name == "irc"
        assert IRCPlugin.version == "1.0.0"

    def test_irc_plugin_initialization_success(self):
        """Test IRC plugin initializes with valid config"""
        config = {
            "enabled": True,
            "server": "irc.example.com",
            "port": 6667,
            "channels": ["#quads"],
            "nickname": "quads-bot",
        }
        plugin = IRCPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.server == "irc.example.com"
        assert plugin.port == 6667

    def test_irc_plugin_initialization_missing_server(self, caplog):
        """Test IRC plugin fails without server"""
        config = {"enabled": True}
        plugin = IRCPlugin(config)
        result = plugin.initialize()

        assert result is False
        assert "server not configured" in caplog.text


class TestSMTPEmailPlugin:
    """Test cases for SMTP Email plugin"""

    def test_email_plugin_metadata(self):
        """Test Email plugin has correct metadata"""
        assert SMTPEmailPlugin.name == "email"
        assert SMTPEmailPlugin.version == "1.0.0"

    def test_email_plugin_initialization_success(self):
        """Test Email plugin initializes with valid config"""
        config = {
            "enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "from_address": "quads@example.com",
        }
        plugin = SMTPEmailPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.smtp_host == "smtp.example.com"
        assert plugin.smtp_port == 587
        assert plugin.from_address == "quads@example.com"

    def test_email_plugin_initialization_missing_server(self, caplog):
        """Test Email plugin fails without SMTP server"""
        config = {"enabled": True}
        plugin = SMTPEmailPlugin(config)
        result = plugin.initialize()

        assert result is False
        assert "smtp_host not configured" in caplog.text


class TestBadfishPlugin:
    """Test cases for Badfish hardware plugin"""

    def test_badfish_plugin_metadata(self):
        """Test Badfish plugin has correct metadata"""
        assert BadfishHardwarePlugin.name == "badfish"
        assert BadfishHardwarePlugin.version == "1.0.0"

    def test_badfish_plugin_initialization_success(self):
        """Test Badfish plugin initializes with valid config"""
        config = {
            "enabled": True,
            "ipmi_username": "admin",
            "ipmi_password": "password",
        }
        plugin = BadfishHardwarePlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.username == "admin"
        assert plugin.password == "password"

    def test_badfish_plugin_initialization_default(self):
        """Test Badfish plugin initializes with minimal config"""
        config = {"enabled": True}
        plugin = BadfishHardwarePlugin(config)
        result = plugin.initialize()

        # Badfish plugin initializes successfully even without credentials
        assert result is True
        assert plugin.username == ""
        assert plugin.password == ""


class TestForemanPlugin:
    """Test cases for Foreman provisioner plugin"""

    def test_foreman_plugin_metadata(self):
        """Test Foreman plugin has correct metadata"""
        assert ForemanProvisionerPlugin.name == "foreman"
        assert ForemanProvisionerPlugin.version == "1.0.0"

    def test_foreman_plugin_initialization_success(self):
        """Test Foreman plugin initializes with valid config"""
        config = {
            "enabled": True,
            "api_url": "https://foreman.example.com",
            "username": "admin",
            "password": "password",
        }
        plugin = ForemanProvisionerPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.url == "https://foreman.example.com"
        assert plugin.username == "admin"

    def test_foreman_plugin_initialization_default(self):
        """Test Foreman plugin initializes with minimal config"""
        config = {"enabled": True}
        plugin = ForemanProvisionerPlugin(config)
        result = plugin.initialize()

        # Foreman plugin initializes even without full config
        assert result is True
        assert plugin.url is None


class TestJuniperPlugin:
    """Test cases for Juniper switch plugin"""

    def test_juniper_plugin_metadata(self):
        """Test Juniper plugin has correct metadata"""
        assert JuniperSwitchPlugin.name == "juniper"
        assert JuniperSwitchPlugin.version == "1.0.0"

    @patch("quads.plugins.builtin.switches.juniper.QuadsApi")
    def test_juniper_plugin_initialization_success(self, mock_quads_api):
        """Test Juniper plugin initializes with valid config"""
        config = {
            "enabled": True,
            "username": "admin",
        }
        plugin = JuniperSwitchPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.username == "admin"
        mock_quads_api.assert_called_once()

    @patch("quads.plugins.builtin.switches.juniper.QuadsApi")
    def test_juniper_plugin_initialization_minimal(self, mock_quads_api):
        """Test Juniper plugin initializes with minimal config"""
        config = {"enabled": True}
        plugin = JuniperSwitchPlugin(config)
        result = plugin.initialize()

        # Juniper plugin initializes even without username
        assert result is True
        assert plugin.username is None


class TestJiraPlugin:
    """Test cases for JIRA ticketing plugin"""

    def test_jira_plugin_metadata(self):
        """Test JIRA plugin has correct metadata"""
        assert JiraTicketingPlugin.name == "jira"
        assert JiraTicketingPlugin.version == "1.0.0"

    def test_jira_plugin_initialization_success(self):
        """Test JIRA plugin initializes with valid config"""
        config = {
            "enabled": True,
            "url": "https://jira.example.com",
            "username": "user",
            "password": "pass",
            "ticket_queue": "QUADS",
        }
        plugin = JiraTicketingPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.url == "https://jira.example.com"
        assert plugin.ticket_queue == "QUADS"

    def test_jira_plugin_initialization_with_token(self):
        """Test JIRA plugin initializes with token auth"""
        config = {
            "enabled": True,
            "url": "https://jira.example.com",
            "token": "token123",
            "ticket_queue": "QUADS",
            "auth_type": "token",
        }
        plugin = JiraTicketingPlugin(config)
        result = plugin.initialize()

        assert result is True
        assert plugin.url == "https://jira.example.com"
        assert plugin.token == "token123"


class TestBuiltinPluginNaming:
    """Test that all built-in plugins follow naming conventions"""

    def test_builtin_plugins_have_names(self):
        """Test that all built-in plugins have name attribute"""
        plugins = [
            SlackPlugin,
            GoogleChatPlugin,
            IRCPlugin,
            SMTPEmailPlugin,
            BadfishHardwarePlugin,
            ForemanProvisionerPlugin,
            JuniperSwitchPlugin,
            JiraTicketingPlugin,
        ]

        for plugin_class in plugins:
            assert hasattr(plugin_class, "name")
            assert plugin_class.name != ""
            assert isinstance(plugin_class.name, str)

    def test_builtin_plugins_have_version(self):
        """Test that all built-in plugins have version attribute"""
        plugins = [
            SlackPlugin,
            GoogleChatPlugin,
            IRCPlugin,
            SMTPEmailPlugin,
            BadfishHardwarePlugin,
            ForemanProvisionerPlugin,
            JuniperSwitchPlugin,
            JiraTicketingPlugin,
        ]

        for plugin_class in plugins:
            assert hasattr(plugin_class, "version")
            assert plugin_class.version != ""
            assert isinstance(plugin_class.version, str)

    def test_builtin_plugins_have_description(self):
        """Test that all built-in plugins have description attribute"""
        plugins = [
            SlackPlugin,
            GoogleChatPlugin,
            IRCPlugin,
            SMTPEmailPlugin,
            BadfishHardwarePlugin,
            ForemanProvisionerPlugin,
            JuniperSwitchPlugin,
            JiraTicketingPlugin,
        ]

        for plugin_class in plugins:
            assert hasattr(plugin_class, "description")
            assert isinstance(plugin_class.description, str)
