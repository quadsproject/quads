"""Tests for Arista switch plugin"""

from types import SimpleNamespace

import pytest
from unittest.mock import MagicMock, patch

from quads.plugins.builtin.switches.arista import AristaSwitchPlugin


class MockInterface:
    """Mock interface object for testing"""

    def __init__(self, name, switch_ip, switch_port, speed="10", switch_vendor="arista"):
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

    def __init__(self, cloud_name="cloud01", vlan=None, qinq=0):
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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
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
    @patch("quads.tools.external.arista.pexpect")
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_speed_uses_documented_gbps(self, mock_get_vlan, mock_ssh_class, mock_pexpect, plugin):
        """Test the plugin passes Gbps and the real driver emits the matching EOS token"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", speed="10")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_get_vlan.return_value = 20

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert "speed forced 10gfull" in calls

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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.return_value = 20

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        assert mock_arista.set_port.call_count == 1

    @pytest.mark.asyncio
    async def test_configure_returns_true_no_matching_interfaces(self, plugin, switch_plugin_manager):
        """Test configure returns True when all interfaces belong to another enabled plugin"""
        from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin

        plugin.plugin_manager = switch_plugin_manager(plugin, JuniperSwitchPlugin(config={"enabled": True}))

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
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_configure_qinq_cloud_uses_set_port(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test a qinq cloud programs the same port type as any other cloud"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.get_host.return_value = mock_host

        mock_old_assignment = MockAssignment("cloud00", vlan=None)
        mock_new_assignment = MockAssignment("cloud01", vlan=None, qinq=1)
        plugin.quads.get_active_cloud_assignment.side_effect = [mock_old_assignment, mock_new_assignment]

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        mock_get_vlan.side_effect = [20]

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is True
        mock_arista.set_port.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    async def test_modify_success(self, mock_arista_class, mock_ssh_class, plugin):
        """Test modify applies VLAN overrides with --change flag"""
        from types import SimpleNamespace

        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1"),
            MockInterface("em2", "10.0.0.1", "Ethernet2"),
            MockInterface("em3", "10.0.0.1", "Ethernet3"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.side_effect = [
            (True, ["   switchport access vlan 10\n"]),
            (True, ["   switchport access vlan 20\n"]),
            (True, ["   switchport access vlan 30\n"]),
        ]
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400", 2: "1402"})

        assert result is True
        assert mock_arista.set_port.call_count == 2
        plugin.logger.info.assert_any_call("Successfully updated switch settings (arista: 10.0.0.1)")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    async def test_modify_qinq_cloud_uses_set_port(self, mock_arista_class, mock_ssh_class, plugin):
        """Test modify programs the same port type on a qinq cloud"""
        from types import SimpleNamespace

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=1)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400"})

        assert result is True
        mock_arista.set_port.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    async def test_modify_skips_other_vendor_interfaces(self, mock_arista_class, mock_ssh_class, plugin):
        """Test modify only touches interfaces owned by this plugin"""
        from types import SimpleNamespace

        interfaces = [
            MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="juniper"),
            MockInterface("em2", "10.0.0.1", "Ethernet2", switch_vendor="arista"),
        ]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400", 1: "1401"})

        assert result is True
        assert mock_arista.set_port.call_count == 1
        mock_arista_class.assert_called_once_with("10.0.0.1", "Ethernet2", "10", "10", "1401", "admin")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_mismatch_returns_false(self, mock_get_vlan, mock_ssh_class, plugin):
        """Test verify returns False on a VLAN mismatch without change"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is False
        appears_warnings = [
            entry
            for entry in plugin.logger.warning.call_args_list
            if entry.args and "appears to be a member" in str(entry.args[0])
        ]
        appears_errors = [
            entry
            for entry in plugin.logger.error.call_args_list
            if entry.args and "appears to be a member" in str(entry.args[0])
        ]
        assert appears_warnings == []
        assert len(appears_errors) == 1

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_speed_mismatch_returns_false(self, mock_get_vlan, mock_ssh_class, plugin):
        """VLAN correct but expected speed missing must fail closed."""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 20\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is False
        plugin.logger.warning.assert_any_call(
            "Interface %s (%s: %s) speed/FEC does not match quads speed %s Gbps",
            "Ethernet1",
            "arista",
            "10.0.0.1",
            "10",
        )

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_change_repairs_speed_mismatch(
        self, mock_get_vlan, mock_ssh_class, mock_arista_class, plugin
    ):
        """--change must re-apply the port when only the speed drifted."""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 20\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is True
        mock_arista.set_port.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_stale_fec_on_lower_speed_returns_false(self, mock_get_vlan, mock_ssh_class, plugin):
        """A 25G port must not keep the 100G-only RS-FEC setting."""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", speed="25")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (
            True,
            [
                "   switchport access vlan 20\n",
                "   speed forced 25gfull\n",
                "   error-correction encoding reed-solomon\n",
            ],
        )
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is False

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_canonicalized_speed_token_passes(self, mock_get_vlan, mock_ssh_class, plugin):
        """EOS may render 'speed forced 10000full' for 'speed forced 10gfull'."""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", speed="10")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10000full\n", "   switchport access vlan 20\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is True
        plugin.logger.warning.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_verify_no_matching_interfaces_returns_true(self, mock_ssh_class, plugin):
        """Test verify returns True when no interfaces belong to this plugin"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="juniper")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is True

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_verify_no_active_assignment_fails_closed(self, mock_ssh_class, mock_arista_class, plugin):
        """A None assignment must fail closed: no fall-through to cloud01
        VLANs and no set_port call (spare-pool / fresh-install path)."""
        mock_host = MockHost(
            "host1.example.com",
            interfaces=[MockInterface("em1", "10.0.0.1", "Ethernet1")],
            cloud=SimpleNamespace(name="cloud01"),
        )
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = None

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is False
        mock_ssh_class.assert_not_called()
        mock_arista_class.assert_not_called()
        plugin.logger.warning.assert_any_call(
            "No active assignment for cloud %s, cannot verify switch configuration." % "cloud01"
        )

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_parse_trunk_native_vlan(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test verify parses trunk native vlan for the last (public) NIC"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        mock_vlan = MockVlan(vlan_id=200)
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=mock_vlan, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (
            True,
            ["   speed forced 10gfull\n", "   switchport mode trunk\n", "   switchport trunk native vlan 200\n"],
        )
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 200

        result = await plugin.verify(host="host1.example.com", change=False)

        assert result is True
        plugin.logger.error.assert_not_called()

    def test_parse_vlan(self):
        """Test _parse_vlan handles access and trunk native lines"""
        plugin = AristaSwitchPlugin(config={"enabled": True, "username": "admin"})
        assert plugin._parse_vlan(["   switchport access vlan 10"]) == "10"
        assert plugin._parse_vlan(["   switchport trunk native vlan 200"]) == "200"
        assert plugin._parse_vlan(["   switchport mode trunk"]) is None
        assert plugin._parse_vlan([]) is None

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    async def test_ls_config_cloud_not_found(self, mock_ssh_class, plugin):
        """Test ls_config handles cloud not found"""
        plugin.quads.get_active_cloud_assignment.return_value = None

        await plugin.ls_config("nonexistent_cloud")

        plugin.logger.error.assert_called_with("Cloud not found.")

    @pytest.mark.asyncio
    async def test_ls_config_no_hosts_returns_false(self, plugin):
        """An empty cloud must not raise IndexError on hosts[0]."""
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", qinq=1)
        plugin.quads.filter_hosts.return_value = []

        result = await plugin.ls_config("cloud01", all=False)

        assert result is False
        plugin.logger.error.assert_called_with("No hosts found on cloud.")

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
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
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

    @pytest.mark.asyncio
    async def test_modify_host_not_found(self, plugin):
        """Test modify handles missing host"""
        plugin.quads.get_host.return_value = None

        result = await plugin.modify("nonexistent.example.com", overrides={0: "1400"})

        assert result is False
        plugin.logger.error.assert_called_with("Hostname not found.")

    @pytest.mark.asyncio
    async def test_modify_no_interfaces(self, plugin):
        """Test modify handles host with no interfaces"""
        mock_host = MockHost("host1.example.com", interfaces=[])
        plugin.quads.get_host.return_value = mock_host

        await plugin.modify("host1.example.com", overrides={0: "1400"})

        plugin.logger.error.assert_called_with("The host has no interfaces defined")

    @pytest.mark.asyncio
    async def test_modify_override_index_out_of_range(self, plugin):
        """Test modify warns when override index exceeds interface count"""
        from types import SimpleNamespace

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01")

        await plugin.modify("host1.example.com", overrides={5: "1400"})

        plugin.logger.warning.assert_any_call("NIC index %d exceeds host interface count (%d), skipping", 6, 1)

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_change_applies_set_port(self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin):
        """Test verify with change applies set_port and reports all_ok"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is True
        mock_arista.set_port.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_change_qinq_cloud_applies_set_port(
        self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin
    ):
        """Test verify repairs a qinq cloud with the same port type as any other cloud"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=1)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 1100

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is True
        mock_arista.set_port.assert_called_once()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_change_set_port_failure_returns_false(
        self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin
    ):
        """Test verify with change reports False when set_port fails"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 20

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = False
        mock_arista_class.return_value = mock_arista

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is False

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    async def test_modify_already_configured(self, mock_arista_class, mock_ssh_class, plugin):
        """Test modify skips interface already on correct VLAN"""
        from types import SimpleNamespace

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   switchport access vlan 1400\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista_class.return_value = mock_arista

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400"})

        assert result is True
        plugin.logger.info.assert_any_call("Interface em1 is already configured for vlan1400")
        mock_arista.set_port.assert_not_called()

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    async def test_modify_set_port_failure(self, mock_arista_class, mock_ssh_class, plugin):
        """Test modify reports failure when set_port fails"""
        from types import SimpleNamespace

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.get_host.return_value = mock_host
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh

        mock_arista = MagicMock()
        mock_arista.set_port.return_value = False
        mock_arista_class.return_value = mock_arista

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400"})

        assert result is False
        plugin.logger.error.assert_any_call("There was something wrong updating switch for em1")

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.Arista")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_public_vlan_change_applies_convert(
        self, mock_get_vlan, mock_arista_class, mock_ssh_class, plugin
    ):
        """Test verify with change converts the last NIC to public trunk"""
        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]
        mock_vlan = MockVlan(vlan_id=200)
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=mock_vlan, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 10\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 200

        mock_arista = MagicMock()
        mock_arista.convert_port_public.return_value = True
        mock_arista_class.return_value = mock_arista

        result = await plugin.verify(host="host1.example.com", change=True)

        assert result is True
        mock_arista.convert_port_public.assert_called_once()
        assert mock_arista_class.call_args.args[-1] == "admin"

    @pytest.mark.asyncio
    @patch("quads.plugins.builtin.switches.arista.SSHHelper")
    @patch("quads.plugins.builtin.switches.arista.get_vlan")
    async def test_verify_ignores_cloud_argument_of_another_cloud(self, mock_get_vlan, mock_ssh_class, plugin):
        """Test verify warns and keeps using the host's own cloud when --cloud names another cloud"""
        from types import SimpleNamespace

        other_cloud = SimpleNamespace(name="cloud09")
        plugin.quads.get_cloud.return_value = other_cloud

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces, cloud=SimpleNamespace(name="cloud01"))
        plugin.quads.filter_hosts.return_value = [mock_host]
        plugin.quads.get_active_cloud_assignment.return_value = MockAssignment("cloud01", vlan=None, qinq=0)

        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, ["   speed forced 10gfull\n", "   switchport access vlan 1100\n"])
        mock_ssh_class.return_value = mock_ssh
        mock_get_vlan.return_value = 1100

        result = await plugin.verify(host="host1.example.com", cloud="cloud09")

        assert result is True

        plugin.quads.get_active_cloud_assignment.assert_called_with("cloud01")
        plugin.logger.warning.assert_any_call("!!!!! cloud09 is ignored, verifying cloud01. !!!!!")

    @pytest.mark.asyncio
    async def test_configure_fails_when_no_plugin_claims_interfaces(self, plugin, switch_plugin_manager):
        """Test configure fails closed when switch_vendor names no enabled switch plugin"""
        from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin

        plugin.plugin_manager = switch_plugin_manager(plugin, JuniperSwitchPlugin(config={"enabled": True}))

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="arista ")]
        plugin.quads.get_host.return_value = MockHost("host1.example.com", interfaces=interfaces)

        result = await plugin.configure("host1.example.com", "cloud00", "cloud01")

        assert result is False
        plugin.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_modify_fails_when_no_plugin_claims_interfaces(self, plugin, switch_plugin_manager):
        """Test modify fails closed when switch_vendor names no enabled switch plugin"""
        from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin

        plugin.plugin_manager = switch_plugin_manager(plugin, JuniperSwitchPlugin(config={"enabled": True}))

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="arista ")]
        plugin.quads.get_host.return_value = MockHost("host1.example.com", interfaces=interfaces)

        result = await plugin.modify("host1.example.com", change=True, overrides={0: "1400"})

        assert result is False
        plugin.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_verify_fails_when_no_plugin_claims_interfaces(self, plugin, switch_plugin_manager):
        """Test verify fails closed when switch_vendor names no enabled switch plugin"""
        from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin

        plugin.plugin_manager = switch_plugin_manager(plugin, JuniperSwitchPlugin(config={"enabled": True}))

        interfaces = [MockInterface("em1", "10.0.0.1", "Ethernet1", switch_vendor="arista ")]
        mock_host = MockHost("host1.example.com", interfaces=interfaces)
        plugin.quads.filter_hosts.return_value = [mock_host]

        result = await plugin.verify(host="host1.example.com")

        assert result is False
        plugin.logger.error.assert_called()


class TestAristaClient:
    """Test cases for the Arista pexpect client"""

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_success(self, mock_pexpect):
        """Test Arista set_port issues the dot1q-tunnel command sequence"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert calls == [
            "terminal length 0",
            "configure terminal",
            "interface Ethernet1",
            "no switchport trunk native vlan",
            "no switchport trunk allowed vlan",
            "switchport mode dot1q-tunnel",
            "switchport access vlan 20",
            "speed forced 25gfull",
            "exit",
            "write memory",
            "copy running-config startup-config",
        ]
        mock_child.expect.assert_any_call(r"[>#]", timeout=120)
        mock_child.expect.assert_any_call("Copy completed", timeout=120)
        mock_child.close.assert_called_once()
        # a text child is required: execute() inspects child.before as str
        mock_pexpect.spawn.assert_called_once_with("ssh -o StrictHostKeyChecking=no admin@10.0.0.1", encoding="utf-8")

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_without_username(self, mock_pexpect):
        """Test a missing plugin username fails before spawning ssh"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", None)

        result = arista.set_port()

        assert result is False
        mock_pexpect.spawn.assert_not_called()

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_timeout(self, mock_pexpect):
        """Test Arista set_port handles SSH timeout"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_pexpect.spawn.return_value = MagicMock()
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")
        mock_pexpect.exceptions.TIMEOUT = type("TIMEOUT", (Exception,), {})
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")

        result = arista.set_port()

        assert result is False

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_100g_uses_auto_speed_with_fec(self, mock_pexpect):
        """100G emits RS-FEC before 'speed auto 100g-2', matching the recipe."""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "100", "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert "error-correction encoding reed-solomon" in calls
        assert "speed auto 100g-2" in calls
        assert not any("speed forced" in c for c in calls)
        assert calls.index("error-correction encoding reed-solomon") < calls.index("speed auto 100g-2")

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_lower_speed_uses_forced_token(self, mock_pexpect):
        """Lowering speed emits the forced token; the recipe does not clear first."""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert "speed forced 25gfull" in calls
        assert "no speed" not in calls
        assert "no error-correction encoding reed-solomon" not in calls
        assert "error-correction encoding reed-solomon" not in calls

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_100g_uses_recipe_sequence(self, mock_pexpect):
        """Raising a port to 100G follows the recipe without clearing first."""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "100", "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert "no speed" not in calls
        assert "error-correction encoding reed-solomon" in calls
        assert "speed auto 100g-2" in calls
        assert calls.index("error-correction encoding reed-solomon") < calls.index("speed auto 100g-2")

    @pytest.mark.parametrize(
        "speed, expected",
        [
            ("1", "speed forced 1000full"),
            ("10", "speed forced 10gfull"),
            ("25", "speed forced 25gfull"),
            ("40", "speed forced 40gfull"),
        ],
    )
    @patch("quads.tools.external.arista.pexpect")
    def test_arista_speed_uses_documented_gbps(self, mock_pexpect, speed, expected):
        """Test documented Gbps inputs map to the EOS speed tokens"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", speed, "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert expected in calls

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_convert_port_public_success(self, mock_pexpect):
        """Test Arista convert_port_public issues the trunk-mode command sequence"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.convert_port_public()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert calls == [
            "terminal length 0",
            "configure terminal",
            "interface Ethernet1",
            "no switchport access vlan",
            "switchport mode trunk",
            "switchport trunk native vlan 20",
            "switchport trunk allowed vlan 20",
            "speed forced 25gfull",
            "exit",
            "write memory",
            "copy running-config startup-config",
        ]
        mock_child.close.assert_called_once()

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_execute_detects_switch_error(self, mock_pexpect):
        """Test execute raises on EOS % error output"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_pexpect.exceptions.TIMEOUT = type("TIMEOUT", (Exception,), {})
        mock_child = MagicMock()
        mock_child.before = "% Invalid input\n"
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is False

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_set_port_no_speed(self, mock_pexpect):
        """Test Arista set_port skips speed when port_speed is falsy"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", None, "10", "20", "admin")

        mock_child = MagicMock()
        mock_pexpect.spawn.return_value = mock_child

        result = arista.set_port()

        assert result is True
        calls = [c.args[0] for c in mock_child.sendline.call_args_list]
        assert "speed" not in " ".join(calls)

    @patch("quads.tools.external.arista.pexpect")
    def test_arista_convert_port_public_timeout(self, mock_pexpect):
        """Test Arista convert_port_public handles timeout"""
        from quads.tools.external.arista import Arista

        arista = Arista("10.0.0.1", "Ethernet1", "25", "10", "20", "admin")

        mock_pexpect.spawn.return_value = MagicMock()
        mock_pexpect.exceptions.TIMEOUT = type("TIMEOUT", (Exception,), {})
        mock_pexpect.spawn.return_value.expect.side_effect = mock_pexpect.exceptions.TIMEOUT("timeout")

        result = arista.convert_port_public()

        assert result is False


class TestSpeedStatementMatching:
    @pytest.mark.parametrize(
        "expected, lines, matches",
        [
            ("speed forced 10gfull", ["speed forced 10000full"], True),
            ("speed forced 10gfull", ["speed forced 10gfull"], True),
            ("speed forced 25gfull", ["   speed forced 25000full\n"], True),
            ("speed forced 1000full", ["speed forced 1000full"], True),
            ("speed auto 100g-2", ["speed auto 100g-2"], True),
            ("speed auto 100g-2", ["speed auto"], True),
            ("speed forced 10gfull", ["speed forced 25gfull"], False),
            ("speed auto 100g-2", ["speed auto 100g-4"], False),
            ("speed forced 25gfull", ["switchport access vlan 20"], False),
        ],
    )
    def test_speed_statement_matches(self, expected, lines, matches):
        """Canonicalized EOS tokens must not report false speed drift."""
        from quads.tools.external.arista import speed_statement_matches

        assert speed_statement_matches(expected, lines) is matches
