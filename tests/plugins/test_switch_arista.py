"""Tests for Arista switch plugin"""

import pytest
from unittest.mock import MagicMock, patch

from quads.plugins.builtin.switches.arista import AristaSwitchPlugin


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


class TestAristaSwitchPlugin:
    """Test cases for AristaSwitchPlugin"""

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
            patch("quads.plugins.builtin.switches.arista.QuadsApi"),
            patch("quads.plugins.builtin.switches.arista.Config"),
        ):
            plugin_obj = AristaSwitchPlugin(config=mock_config)
            plugin_obj.quads = MagicMock()
            plugin_obj.logger = MagicMock()
            plugin_obj.initialize()
            return plugin_obj

    def test_plugin_metadata(self):
        """Test plugin has correct metadata"""
        assert AristaSwitchPlugin.name == "arista"
        assert AristaSwitchPlugin.version == "1.0.0"
        assert AristaSwitchPlugin.description == "Arista switch plugin"
        assert AristaSwitchPlugin.author == "QUADS Team"

    def test_initialize_success(self, mock_config):
        """Test plugin initializes successfully"""
        with (
            patch("quads.plugins.builtin.switches.arista.QuadsApi"),
            patch("quads.plugins.builtin.switches.arista.Config"),
        ):
            plugin = AristaSwitchPlugin(config=mock_config)
            result = plugin.initialize()

            assert result is True
            assert hasattr(plugin, "quads")
            assert plugin.username == "admin"

    def test_initialize_no_username(self):
        """Test plugin initializes without username"""
        with (
            patch("quads.plugins.builtin.switches.arista.QuadsApi"),
            patch("quads.plugins.builtin.switches.arista.Config"),
        ):
            plugin = AristaSwitchPlugin(config={})
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
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_success_simple(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure succeeds with simple VLAN change"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 20, 10, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_ssh.disconnect.assert_called()
        assert mock_arista.set_port.called

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_configure_ssh_connection_failure(self, mock_ssh_class, plugin):
        """Test configure handles SSH connection failure"""
        from quads.tools.external.ssh_helper import SSHHelperException

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00")
        mock_new_assignment = MockAssignment("cloud01")
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh_class.side_effect = SSHHelperException("Connection failed")

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called_with("Failed to connect to switch: 10.0.0.1")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_no_vlan_detected_warning(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure warns when no VLAN is detected"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, []),
            (True, ["   switchport access vlan 20\n"]),
        ]
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 20, 20, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        plugin.logger.warning.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_public_vlan_conversion(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure handles public VLAN conversion"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista.convert_port_public.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 20, 10, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_arista.convert_port_public.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_arista_set_port_failure(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure handles Arista set_port failure"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["   switchport access vlan 10\n"]),
            (True, ["   switchport access vlan 10\n"]),
        ]
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = False
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called()
        mock_ssh.disconnect.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_arista_convert_port_public_failure(
        self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin
    ):
        """Test configure handles Arista convert_port_public failure"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.convert_port_public.return_value = False
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called()
        mock_ssh.disconnect.assert_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_multiple_switches(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure handles multiple switches"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.2", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [10, 20, 10, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        assert mock_ssh.disconnect.call_count >= 1

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_same_vlan_no_change(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure skips interfaces already on correct VLAN"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 20\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [20, 20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_arista.set_port.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_public_vlan_same_as_old(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test configure skips public VLAN change when already correct"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_vlan = MockVlan(vlan_id=200)
        mock_new_assignment = MockAssignment("cloud01", vlan=mock_new_vlan)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 200\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [200, 200]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_arista.convert_port_public.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_skips_other_vendor_interfaces(
        self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin
    ):
        """Test configure skips interfaces with a different switch_vendor"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="arista"),
            MockInterface("em2", "10.0.0.1", "Ethernet2", switch_vendor="juniper"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.return_value = 20

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        assert mock_arista.set_port.call_count == 1

    @pytest.mark.asyncio
    async def test_configure_returns_true_no_matching_interfaces(self, plugin):
        """Test configure returns True when all interfaces belong to other vendors"""
        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="juniper"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00")
        mock_new_assignment = MockAssignment("cloud01")
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_cloud_not_found(self, mock_ssh_class, plugin):
        """Test ls_config handles cloud not found"""
        plugin.quads.get_active_cloud_assignment.return_value = None

        await plugin.ls_config("nonexistent_cloud")

        plugin.logger.error.assert_called_with("Cloud not found.")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_single_host(self, mock_ssh_class, plugin):
        """Test ls_config for single host"""
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["   switchport access vlan 10\n"]),
            (True, ["   switchport access vlan 20\n"]),
        ]
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.info.assert_any_call("Cloud qinq: 1")
        assert mock_ssh.disconnect.called

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_all_hosts(self, mock_ssh_class, plugin):
        """Test ls_config for all hosts"""
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces1 = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host1 = MockHost("host1.example.com", interfaces=interfaces1)

        interfaces2 = [MockInterface("em1", "10.0.0.1", "Ethernet2")]
        mock_host2 = MockHost("host2.example.com", interfaces=interfaces2)

        plugin.quads.filter_hosts.return_value = [mock_host1, mock_host2]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=True)

        plugin.logger.info.assert_any_call("host1.example.com:")
        plugin.logger.info.assert_any_call("host2.example.com:")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_no_interfaces(self, mock_ssh_class, plugin):
        """Test ls_config handles hosts with no interfaces"""
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        mock_host = MockHost("host1.example.com", interfaces=[])
        plugin.quads.filter_hosts.return_value = [mock_host]

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.error.assert_called_with("The cloud has no hosts or the host has no interfaces defined")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_vlan_detection_failure(self, mock_ssh_class, plugin):
        """Test ls_config handles VLAN detection failure"""
        mock_assignment = MockAssignment("cloud01", qinq=1)
        plugin.quads.get_active_cloud_assignment.return_value = mock_assignment

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_class.return_value = mock_ssh

        await plugin.ls_config("cloud01", all=False)

        plugin.logger.warning.assert_called()
        assert "Could not determine the previous VLAN member" in plugin.logger.warning.call_args[0][0]


class TestAristaClient:
    """Test cases for the Arista pexpect client"""

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_success(self, mock_pexpect, mock_config):
        """Test Arista set_port succeeds"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "10", "20")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        mock_child.close.assert_called_once()

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_timeout(self, mock_pexpect, mock_config):
        """Test Arista set_port handles SSH timeout"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "10", "20")

        mock_pexpect.spawn.return_value = MagicMock()
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")
        mock_pexpect.exceptions.TIMEOUT = type("TIMEOUT", (Exception,), {})
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")

        result = arista.set_port()

        assert result is False

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_convert_port_public_success(self, mock_pexpect, mock_config):
        """Test Arista convert_port_public succeeds"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "10", "20")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.convert_port_public()

        assert result is True
        mock_child.close.assert_called_once()

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_convert_port_public_timeout(self, mock_pexpect, mock_config):
        """Test Arista convert_port_public handles timeout"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "10", "20")

        mock_pexpect.spawn.return_value = MagicMock()
        mock_pexpect.exceptions.TIMEOUT = type("TIMEOUT", (Exception,), {})
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")

        result = arista.convert_port_public()

        assert result is False

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_no_old_vlan(self, mock_pexpect, mock_config):
        """Test Arista set_port skips old VLAN removal when old_vlan is 0"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "0", "20")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [str(c) for c in mock_child.sendline.call_args_list]
        assert not any("no vlan 0" in c for c in calls)

    @patch("quads.tools.external.arista.Config")
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_convert_port_public_same_vlan(self, mock_pexpect, mock_config):
        """Test convert_port_public skips old VLAN removal when same as new"""
        mock_config.plugins = {"arista": {"username": "admin"}}

        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "1000", "20", "20")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.convert_port_public()

        assert result is True
        calls = [str(c) for c in mock_child.sendline.call_args_list]
        assert not any("no vlan 20" in c for c in calls)
