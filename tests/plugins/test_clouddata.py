"""Tests for clouddata dayzero plugin"""

import asyncio
import pytest
import yaml
from unittest.mock import MagicMock, patch


class TestCloudDataPluginMetadata:
    """Test CloudDataPlugin metadata"""

    def test_metadata(self):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        assert CloudDataPlugin.name == "clouddata"
        assert CloudDataPlugin.version == "1.0.0"
        assert CloudDataPlugin.run_mode == "per_cloud"

    def test_initialize(self):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        plugin = CloudDataPlugin({"enabled": True})
        assert plugin.initialize() is True


class TestCloudDataPluginExecute:
    """Test CloudDataPlugin execute logic"""

    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_no_active_assignment(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.get_active_cloud_assignment.return_value = None

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True
        plugin.logger.info.assert_called()

    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_no_current_schedules(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_api.get_current_schedules.return_value = []

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "rdu2", "ticket_url": "https://issues.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_yaml_content_structure(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud02"
        mock_assignment.id = 42
        mock_assignment.ticket = "SCALELAB-12345"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched1 = MagicMock()
        sched1.host.name = "host01.example.com"
        sched2 = MagicMock()
        sched2.host.name = "host02.example.com"
        mock_api.get_current_schedules.return_value = [sched1, sched2]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_cls.return_value = mock_ssh

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True

        call_args = mock_ssh.run_cmd.call_args[0][0]
        import base64
        import re

        match = re.search(r"echo '([^']+)'", call_args)
        assert match is not None
        decoded = base64.b64decode(match.group(1)).decode()
        data = yaml.safe_load(decoded)

        assert data["cloud_name"] == "cloud02"
        assert data["assignment_id"] == 42
        assert data["bmc_user"] == "quads"
        assert data["bmc_pass"] == "rdu2@SCALELAB-12345"
        assert data["cloud_systems"] == ["host01.example.com", "host02.example.com"]
        assert data["cloud_ticket"] == "https://issues.example.com/browse/SCALELAB-12345"

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "rdu2", "ticket_url": "https://issues.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_hosts_sorted(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud02"
        mock_assignment.id = 1
        mock_assignment.ticket = "TICKET-1"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched_c = MagicMock()
        sched_c.host.name = "host03.example.com"
        sched_a = MagicMock()
        sched_a.host.name = "host01.example.com"
        sched_b = MagicMock()
        sched_b.host.name = "host02.example.com"
        mock_api.get_current_schedules.return_value = [sched_c, sched_a, sched_b]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_cls.return_value = mock_ssh

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True

        call_args = mock_ssh.run_cmd.call_args[0][0]
        import base64
        import re

        match = re.search(r"echo '([^']+)'", call_args)
        decoded = base64.b64decode(match.group(1)).decode()
        data = yaml.safe_load(decoded)
        assert data["cloud_systems"] == [
            "host01.example.com",
            "host02.example.com",
            "host03.example.com",
        ]

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "rdu2", "ticket_url": "https://issues.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_first_host_only(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud02"
        mock_assignment.id = 1
        mock_assignment.ticket = "TICKET-1"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched1 = MagicMock()
        sched1.host.name = "host01.example.com"
        sched2 = MagicMock()
        sched2.host.name = "host02.example.com"
        mock_api.get_current_schedules.return_value = [sched1, sched2]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_cls.return_value = mock_ssh

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        asyncio.run(plugin.execute("cloud02"))

        mock_ssh_cls.assert_called_once_with("host01.example.com")

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "rdu2", "ticket_url": "https://issues.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_ssh_delivery_failure(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin, SSHHelperException

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud02"
        mock_assignment.id = 1
        mock_assignment.ticket = "TICKET-1"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched1 = MagicMock()
        sched1.host.name = "host01.example.com"
        mock_api.get_current_schedules.return_value = [sched1]

        mock_ssh_cls.side_effect = SSHHelperException("Connection refused")

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is False

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "rdu2", "ticket_url": "https://issues.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_ssh_cmd_failure(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud02"
        mock_assignment.id = 1
        mock_assignment.ticket = "TICKET-1"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched1 = MagicMock()
        sched1.host.name = "host01.example.com"
        mock_api.get_current_schedules.return_value = [sched1]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (False, ["Permission denied"])
        mock_ssh_cls.return_value = mock_ssh

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is False

    @patch("quads.plugins.builtin.dayzero.clouddata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.clouddata.Config", {"ipmi_cloud_username": "quads", "infra_location": "lab1", "ticket_url": "https://jira.lab1.example.com/browse"})
    @patch("quads.plugins.builtin.dayzero.clouddata.QuadsApi")
    def test_bmc_pass_construction(self, mock_api_cls, mock_ssh_cls):
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api

        mock_assignment = MagicMock()
        mock_assignment.cloud.name = "cloud05"
        mock_assignment.id = 99
        mock_assignment.ticket = "JIRA-7890"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment

        sched1 = MagicMock()
        sched1.host.name = "host01.example.com"
        mock_api.get_current_schedules.return_value = [sched1]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_cls.return_value = mock_ssh

        plugin = CloudDataPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        asyncio.run(plugin.execute("cloud05"))

        call_args = mock_ssh.run_cmd.call_args[0][0]
        import base64
        import re

        match = re.search(r"echo '([^']+)'", call_args)
        decoded = base64.b64decode(match.group(1)).decode()
        data = yaml.safe_load(decoded)
        assert data["bmc_pass"] == "lab1@JIRA-7890"


class TestCloudDataDiscovery:
    """Test that clouddata plugin is discoverable"""

    def test_clouddata_discovered(self):
        from quads.plugins.discovery import PluginDiscovery
        from quads.plugins.builtin.dayzero.clouddata import CloudDataPlugin

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("quads.plugins.builtin.dayzero")
        assert "clouddata" in plugins
        assert plugins["clouddata"] is CloudDataPlugin
