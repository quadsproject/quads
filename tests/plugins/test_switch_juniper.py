"""Tests for Juniper switch plugin"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin


class MockInterface:
    """Mock interface object for testing"""

    def __init__(self, name, switch_ip, switch_port, speed="1000", switch_vendor=None):
        self.name = name
        self.switch_ip = switch_ip
        self.switch_port = switch_port
        self.speed = speed
        self.switch_vendor = switch_vendor


class MockHost:
    """Mock host object for testing"""

    def __init__(self, name, interfaces=None, cloud=None):
        self.name = name
        self.interfaces = interfaces or []
        self.cloud = cloud or MagicMock(name="cloud01")


class MockAssignment:
    """Mock assignment object for testing"""

    def __init__(self, cloud_name="cloud01", vlan=None, qinq=1):
        self.cloud = MagicMock(name=cloud_name)
        self.vlan = vlan
        self.qinq = qinq


class MockVlan:
    """Mock VLAN object for testing"""

    def __init__(self, vlan_id=100):
        self.vlan_id = vlan_id


class TestJuniperSwitchPlugin:
    """Test cases for JuniperSwitchPlugin"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        return {
            "enabled": True,
            "username": "admin",
        }

    @pytest.fixture
    def plugin(self, mock_config):
        """Create plugin instance with mocked dependencies"""
        with (
            patch("quads.plugins.builtin.switches.juniper.QuadsApi"),
            patch("quads.plugins.builtin.switches.juniper.Config"),
        ):
            plugin_obj = JuniperSwitchPlugin(config=mock_config)
            plugin_obj.quads = MagicMock()
            plugin_obj.logger = MagicMock()
            plugin_obj.initialize()
            return plugin_obj

    def test_plugin_metadata(self):
        """Test plugin has correct metadata"""
        assert JuniperSwitchPlugin.name == "juniper"
        assert JuniperSwitchPlugin.version == "1.0.0"
        assert JuniperSwitchPlugin.description == "Juniper switch plugin"
        assert JuniperSwitchPlugin.author == "QUADS Team"

    def test_initialize_success(self, mock_config):
        """Test plugin initializes successfully"""
        with (
            patch("quads.plugins.builtin.switches.juniper.QuadsApi"),
            patch("quads.plugins.builtin.switches.juniper.Config"),
        ):
            plugin = JuniperSwitchPlugin(config=mock_config)
            result = plugin.initialize()

            assert result is True
            assert hasattr(plugin, "quads")
            assert plugin.username == "admin"

    def test_initialize_no_username(self):
        """Test plugin initializes without username"""
        with (
            patch("quads.plugins.builtin.switches.juniper.QuadsApi"),
            patch("quads.plugins.builtin.switches.juniper.Config"),
        ):
            plugin = JuniperSwitchPlugin(config={})
            result = plugin.initialize()

            assert result is True
            assert plugin.username is None

    @pytest.mark.asyncio
    async def test_configure_host_no_interfaces(self, plugin):
        """Test configure fails when host has no interfaces"""
        mock_host = MockHost("host1.example.com", interfaces=[])
        plugin.quads.get_host.return_value = mock_host

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called_with("Host has no interfaces defined.")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_success_simple(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure succeeds with simple VLAN change"""
        # Setup mocks
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = True
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [10, 20, 10, 20]  # old_cloud old, new_cloud new for each interface

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_ssh.disconnect.assert_called()
        assert mock_juniper.set_port.called

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_configure_ssh_connection_failure(self, mock_ssh_class, plugin):
        """Test configure handles SSH connection failure"""
        from quads.tools.external.ssh_helper import SSHHelperException

        # Setup mocks
        interfaces = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00")
        mock_new_assignment = MockAssignment("cloud01")
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH to fail
        mock_ssh_class.side_effect = SSHHelperException("Connection failed")

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called_with("Failed to connect to switch: 10.0.0.1")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_no_vlan_detected_warning(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure warns when no VLAN is detected"""
        # Setup mocks - use 2 interfaces, first one not being last_nic
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock to return empty result (no VLAN detected for first interface)
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, []),  # First interface - no VLAN detected (triggers warning)
            (True, ["members QinQ_vl20;"]),  # Second interface - has VLAN
        ]
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = True
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [10, 20, 20, 20]  # old/new for each interface

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        # Warning should be logged when no VLAN is detected
        plugin.logger.warning.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_public_vlan_conversion(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure handles public VLAN conversion"""
        # Setup mocks
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),  # Last interface
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = True
        mock_juniper.convert_port_public.return_value = True
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [10, 20, 10, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_juniper.convert_port_public.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_juniper_set_port_failure(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure handles Juniper set_port failure"""
        # Setup mocks - use 2 interfaces so first is NOT last_nic
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock - return VLAN 10 for first interface
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["members QinQ_vl10;"]),  # First interface
            (True, ["members QinQ_vl10;"]),  # Second interface (won't be reached)
        ]
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock to fail on first interface
        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = False
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock - ensure old != new for first interface
        mock_get_vlan.side_effect = [10, 20]  # old=10, new=20 so they differ

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        # Should return False due to set_port failure
        assert result is False
        plugin.logger.error.assert_called()
        mock_ssh.disconnect.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_juniper_convert_port_public_failure(
        self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin
    ):
        """Test configure handles Juniper convert_port_public failure"""
        # Setup mocks
        interfaces = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock to fail
        mock_juniper = MagicMock()
        mock_juniper.convert_port_public.return_value = False
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [10, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called()
        mock_ssh.disconnect.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_multiple_switches(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure handles multiple switches"""
        # Setup mocks with interfaces on different switches
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.2", "ge-0/0/2"),  # Different switch
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = True
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [10, 20, 10, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        # Should disconnect and reconnect for different switch
        assert mock_ssh.disconnect.call_count >= 1

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_same_vlan_no_change(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure skips interfaces already on correct VLAN"""
        # Setup mocks
        interfaces = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl20;"])  # Already on vlan 20
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock - old and new VLANs are the same
        mock_get_vlan.side_effect = [20, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        # set_port should not be called since VLANs match
        mock_juniper.set_port.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_cloud_not_found(self, mock_ssh_class, plugin):
        """Test ls_config handles cloud not found"""
        plugin.quads.get_active_cloud_assignment.return_value = None

        await plugin.ls_config("nonexistent_cloud")

        plugin.logger.error.assert_called_with("Cloud not found.")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_single_host(self, mock_ssh_class, plugin):
        """Test ls_config for single host"""
        # Setup mocks
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["set vlans QinQ_vl10 vlan-id 10;"]),  # First interface
            (True, ["members QinQ_vl20;"]),  # Last interface
        ]
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.info.assert_any_call("Cloud qinq: 1")
        assert mock_ssh.disconnect.called

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_all_hosts(self, mock_ssh_class, plugin):
        """Test ls_config for all hosts"""
        # Setup mocks
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces1 = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host1 = MockHost("host1.example.com", interfaces=interfaces1)

        interfaces2 = [MockInterface("em1", "10.0.0.1", "ge-0/0/2")]
        mock_host2 = MockHost("host2.example.com", interfaces=interfaces2)

        plugin.quads.filter_hosts.return_value = [mock_host1, mock_host2]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=True)

        plugin.logger.info.assert_any_call("host1.example.com:")
        plugin.logger.info.assert_any_call("host2.example.com:")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_no_interfaces(self, mock_ssh_class, plugin):
        """Test ls_config handles hosts with no interfaces"""
        # Setup mocks
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        mock_host = MockHost("host1.example.com", interfaces=[])
        plugin.quads.filter_hosts.return_value = [mock_host]

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.error.assert_called_with("The cloud has no hosts or the host has no interfaces defined")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_vlan_detection_failure(self, mock_ssh_class, plugin):
        """Test ls_config handles VLAN detection failure"""
        # Setup mocks
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        # Setup SSH helper mock to throw IndexError
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])  # Empty result causes IndexError
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.warning.assert_called()
        assert "Could not determine the previous VLAN member" in plugin.logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    async def test_ls_config_last_interface_qinq_vlan(self, mock_ssh_class, plugin):
        """Test ls_config detects QinQ VLAN on last interface"""
        # Setup mocks
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        # Setup SSH helper mock
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["set vlans QinQ_vl10 vlan-id 10;"]),  # First interface
            (True, ["members QinQ_vl200;"]),  # Last interface with QinQ prefix
        ]
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=False)

        # Should log VLAN 200 (stripped from QinQ_vl200)
        plugin.logger.info.assert_any_call("Interface em2 appears to be a member of VLAN 200")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_public_vlan_same_as_old(self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin):
        """Test configure skips public VLAN change when already correct"""
        # Setup mocks
        interfaces = [MockInterface("em1", "10.0.0.1", "ge-0/0/1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        # Setup SSH helper mock - already on vlan 200
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl200;"])
        mock_ssh_class.return_value = mock_ssh

        # Setup Juniper mock
        mock_juniper = MagicMock()
        mock_juniper_class.return_value = mock_juniper

        # Setup get_vlan mock
        mock_get_vlan.side_effect = [200, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        # convert_port_public should not be called since VLANs match
        mock_juniper.convert_port_public.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.juniper.SSHHelper")
    @patch("quads.plugins.builtin.switches.juniper.Juniper")
    @patch("quads.plugins.builtin.switches.juniper.get_vlan")
    async def test_configure_skips_other_vendor_interfaces(
        self, mock_get_vlan, mock_juniper_class, mock_ssh_class, plugin
    ):
        """Test configure skips interfaces with a different switch_vendor"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1", switch_vendor="juniper"),
            MockInterface("em2", "10.0.0.1", "ge-0/0/2", switch_vendor="arista"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["members QinQ_vl10;"])
        mock_ssh_class.return_value = mock_ssh

        mock_juniper = MagicMock()
        mock_juniper.set_port.return_value = True
        mock_juniper_class.return_value = mock_juniper

        mock_get_vlan.return_value = 20

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        assert mock_juniper.set_port.call_count == 1

    @pytest.mark.asyncio
    async def test_configure_returns_true_no_matching_interfaces(self, plugin):
        """Test configure returns True when all interfaces belong to other vendors"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "ge-0/0/1", switch_vendor="arista"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00")
        mock_new_assignment = MockAssignment("cloud01")
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
