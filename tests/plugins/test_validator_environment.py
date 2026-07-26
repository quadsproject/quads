"""Tests for environment validator plugin"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open
from datetime import datetime, timedelta
from typing import List

from quads.plugins.builtin.validators.environment import EnvironmentValidatorPlugin
from quads.plugins.manager import PluginManager


class MockHost:
    """Mock host object for testing"""

    def __init__(
        self,
        name,
        rack=None,
        uloc=None,
        blade=None,
        switch_config_applied=True,
        cloud=None,
        default_cloud=None,
        interfaces=None,
    ):
        self.name = name
        self.rack = rack
        self.uloc = uloc
        self.blade = blade
        self.switch_config_applied = switch_config_applied
        self.cloud = cloud or MagicMock(name="cloud01")
        self.default_cloud = default_cloud or MagicMock(name="cloud00")
        self.interfaces = interfaces or []


class MockAssignment:
    """Mock assignment object for testing"""

    def __init__(
        self,
        cloud="cloud01",
        owner="testuser",
        ticket="TICKET-123",
        vlan=None,
        notification=None,
        assignment_id=1,
    ):
        self.cloud = MagicMock(name=cloud)
        self.owner = owner
        self.ticket = ticket
        self.vlan = vlan
        self.notification = notification or MagicMock(success=False, fail=False, id=1)
        self.id = assignment_id


class MockSchedule:
    """Mock schedule object for testing"""

    def __init__(self, start=None, assignment=None):
        self.start = start or datetime.now()
        self.assignment = assignment or MockAssignment()


class TestEnvironmentValidatorPlugin:
    """Test cases for EnvironmentValidatorPlugin"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = {
            "enabled": True,
            "validation_grace_period": 60,
            "domain": "example.com",
            "infra_location": "rdu2",
            "FPING_TIMEOUT": 2000,
            "TEMPLATES_PATH": "/opt/quads/templates",
            "INTERFACES": {
                "em1": ["172.16.0.0", "172.17.0.0"],
                "em2": ["172.18.0.0", "172.19.0.0"],
            },
            "ipmi_cloud_username_id": 4,
            "plugins": {
                "email": {"report_cc": "admin@example.com,devops@example.com"},
                "foreman": {"api_url": "https://foreman.example.com"},
                "badfish": {"ipmi_username": "root", "ipmi_password": "password"},
            },
        }
        return config

    @pytest.fixture
    def plugin(self, mock_config):
        """Create plugin instance with mocked dependencies"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.QuadsApi"),
            patch("quads.plugins.builtin.validators.environment.get_hardware_dispatcher"),
            patch("quads.plugins.builtin.validators.environment.get_switch_dispatcher"),
            patch("quads.plugins.builtin.validators.environment.get_email_dispatcher"),
        ):
            # Configure Config mock to support both dict and attribute access
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            mock_cfg.__contains__ = lambda self, key: key in mock_config
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            plugin_obj = EnvironmentValidatorPlugin(config={})
            plugin_obj.quads = MagicMock()
            plugin_obj.hardware_dispatcher = AsyncMock()
            plugin_obj.switch_dispatcher = AsyncMock()
            # Make email_dispatcher methods async
            plugin_obj.email_dispatcher = MagicMock()
            plugin_obj.email_dispatcher.send_mail = AsyncMock()
            plugin_obj.logger = MagicMock()
            plugin_obj.initialize()
            return plugin_obj

    def test_plugin_metadata(self):
        """Test plugin has correct metadata"""
        assert EnvironmentValidatorPlugin.name == "environment"
        assert EnvironmentValidatorPlugin.version == "1.0.0"
        assert EnvironmentValidatorPlugin.description == "Standard environment validation for QUADS"
        assert EnvironmentValidatorPlugin.author == "QUADS Team"

    def test_initialize_success(self, mock_config):
        """Test plugin initializes successfully"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.QuadsApi"),
            patch("quads.plugins.builtin.validators.environment.get_hardware_dispatcher"),
            patch("quads.plugins.builtin.validators.environment.get_switch_dispatcher"),
            patch("quads.plugins.builtin.validators.environment.get_email_dispatcher"),
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            plugin = EnvironmentValidatorPlugin(config={})
            result = plugin.initialize()

            assert result is True
            assert hasattr(plugin, "quads")
            assert hasattr(plugin, "hardware_dispatcher")
            assert hasattr(plugin, "switch_dispatcher")
            assert hasattr(plugin, "email_dispatcher")

    @pytest.mark.asyncio
    async def test_notify_failure(self, plugin, mock_config):
        """Test failure notification sends correctly"""
        template_content = "Validation failed for {{cloud}}/{{owner}}/{{ticket}}\nReport: {{report}}"

        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with (
            patch("builtins.open", mock_open(read_data=template_content)),
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
        ):
            # Setup Config mock to return proper values
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            mock_cfg.plugins = mock_config["plugins"]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            cloud = "cloud01"
            owner = "testuser"
            ticket = "TICKET-123"
            report = "Test failure report"

            await plugin.notify_failure(cloud, owner, ticket, report)

            # Verify email dispatcher was called with correct parameters
            plugin.email_dispatcher.send_mail.assert_called_once()
            call_args = plugin.email_dispatcher.send_mail.call_args
            assert "Validation check failed" in call_args.kwargs["subject"]
            assert cloud in call_args.kwargs["subject"]
            assert owner in call_args.kwargs["subject"]
            assert ticket in call_args.kwargs["subject"]
            assert call_args.kwargs["recipients"] == [f"{owner}@{mock_config['domain']}"]
            assert "admin@example.com" in call_args.kwargs["cc"]
            assert "devops@example.com" in call_args.kwargs["cc"]

    @pytest.mark.asyncio
    async def test_notify_success(self, plugin, mock_config):
        """Test success notification sends correctly"""
        template_content = "Validation succeeded for {{cloud}}/{{owner}}/{{ticket}}"

        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with patch("builtins.open", mock_open(read_data=template_content)):
            cloud = "cloud01"
            owner = "testuser"
            ticket = "TICKET-123"

            await plugin.notify_success(cloud, owner, ticket)

            # Verify email dispatcher was called with correct parameters
            plugin.email_dispatcher.send_mail.assert_called_once()
            call_args = plugin.email_dispatcher.send_mail.call_args
            assert "Validation check succeeded" in call_args.kwargs["subject"]
            assert cloud in call_args.kwargs["subject"]
            assert owner in call_args.kwargs["subject"]
            assert ticket in call_args.kwargs["subject"]
            assert call_args.kwargs["recipients"] == [f"{owner}@{mock_config['domain']}"]

    @pytest.mark.asyncio
    async def test_env_allocation_time_exceeded_true(self, plugin, mock_config):
        """Test env_allocation_time_exceeded returns True when time exceeded"""
        with patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg:
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            cloud = "cloud01"
            old_start = datetime.now() - timedelta(minutes=120)  # 2 hours ago
            mock_schedule = MockSchedule(start=old_start)

            plugin.quads.get_current_schedules.return_value = [mock_schedule]

            result = await plugin.env_allocation_time_exceeded(cloud)

            assert result is True
            plugin.quads.get_current_schedules.assert_called_once_with({"cloud": cloud})

    @pytest.mark.asyncio
    async def test_env_allocation_time_exceeded_false_within_grace(self, plugin):
        """Test env_allocation_time_exceeded returns False within grace period"""
        cloud = "cloud01"
        recent_start = datetime.now() - timedelta(minutes=30)  # 30 minutes ago
        mock_schedule = MockSchedule(start=recent_start)

        plugin.quads.get_current_schedules.return_value = [mock_schedule]

        result = await plugin.env_allocation_time_exceeded(cloud)

        assert result is False
        plugin.logger.warning.assert_called_once()
        assert "grace period" in plugin.logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_env_allocation_time_exceeded_no_schedules(self, plugin):
        """Test env_allocation_time_exceeded returns False when no schedules"""
        cloud = "cloud01"
        plugin.quads.get_current_schedules.return_value = []

        result = await plugin.env_allocation_time_exceeded(cloud)

        assert result is False

    @pytest.mark.asyncio
    async def test_post_system_test_foreman_credentials_invalid(self, plugin, mock_config):
        """Test post_system_test handles invalid Foreman credentials"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = False
            mock_foreman_class.return_value = mock_foreman

            cloud = "cloud01"
            ticket = "TICKET-123"
            hosts = [MockHost("host1.example.com")]
            report = ""

            result, updated_report = await plugin.post_system_test(cloud, ticket, hosts, report)

            assert result is False
            assert "Unable to query Foreman" in updated_report
            assert cloud in updated_report
            plugin.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_post_system_test_hosts_in_build_mode(self, plugin, mock_config):
        """Test post_system_test handles hosts marked for build (Dell path)"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            plugin.hardware_dispatcher.init = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.get_vendor = MagicMock(return_value="Dell")
            plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.set_next_boot_pxe = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.reboot_server = AsyncMock()

            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            result, updated_report = await plugin.post_system_test("cloud01", "TICKET-123", hosts, "")

            assert result is False
            assert "marked for build" in updated_report
            plugin.hardware_dispatcher.init.assert_called_once()
            plugin.hardware_dispatcher.boot_to_type.assert_called_once()
            plugin.hardware_dispatcher.set_next_boot_pxe.assert_not_called()
            plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_system_test_hosts_in_build_mode_non_dell(self, plugin, mock_config):
        """Test post_system_test uses PXE boot for non-Dell hosts in build mode"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            plugin.hardware_dispatcher.init = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.get_vendor = MagicMock(return_value="HPE")
            plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.set_next_boot_pxe = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.reboot_server = AsyncMock()

            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            result, updated_report = await plugin.post_system_test("cloud01", "TICKET-123", hosts, "")

            assert result is False
            assert "marked for build" in updated_report
            plugin.hardware_dispatcher.set_next_boot_pxe.assert_called_once()
            plugin.hardware_dispatcher.boot_to_type.assert_not_called()
            plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_system_test_boot_to_type_failure_skips_reboot(self, plugin, mock_config):
        """Test that reboot is skipped when boot_to_type fails for Dell hosts"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            plugin.hardware_dispatcher.init = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.get_vendor = MagicMock(return_value="Dell")
            plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=False)
            plugin.hardware_dispatcher.reboot_server = AsyncMock()

            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            result, updated_report = await plugin.post_system_test("cloud01", "TICKET-123", hosts, "")

            assert result is False
            assert "host1.example.com" in updated_report
            plugin.hardware_dispatcher.boot_to_type.assert_called_once()
            plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_system_test_set_next_boot_pxe_failure_skips_reboot(self, plugin, mock_config):
        """Test that reboot is skipped when set_next_boot_pxe fails for non-Dell hosts"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            plugin.hardware_dispatcher.init = AsyncMock(return_value=True)
            plugin.hardware_dispatcher.get_vendor = MagicMock(return_value="HPE")
            plugin.hardware_dispatcher.set_next_boot_pxe = AsyncMock(return_value=False)
            plugin.hardware_dispatcher.reboot_server = AsyncMock()

            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            result, updated_report = await plugin.post_system_test("cloud01", "TICKET-123", hosts, "")

            assert result is False
            assert "host1.example.com" in updated_report
            plugin.hardware_dispatcher.set_next_boot_pxe.assert_called_once()
            plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_system_test_hosts_in_build_mode_supermicro(self, plugin, mock_config):
        """Test post_system_test uses raw ipmitool for Supermicro hosts in build mode"""
        supermicro_config = dict(mock_config)
        supermicro_config["plugins"] = dict(mock_config["plugins"])
        supermicro_config["plugins"]["badfish"] = {
            "ipmi_username": "root",
            "ipmi_password": "password",
        }

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.is_supermicro", return_value=True),
            patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class,
        ):
            for key, value in supermicro_config.items():
                setattr(mock_cfg, key, value)

            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ipmi = AsyncMock()
            mock_ipmi.pxe_persistent = AsyncMock(return_value=True)
            mock_ipmi_class.return_value = mock_ipmi

            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            result, updated_report = await plugin.post_system_test("cloud01", "TICKET-123", hosts, "")

            assert result is False
            assert "marked for build" in updated_report
            mock_ipmi.pxe_persistent.assert_called_once()
            plugin.hardware_dispatcher.init.assert_not_called()
            plugin.hardware_dispatcher.boot_to_type.assert_not_called()
            plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_system_test_no_build_hosts(self, plugin, mock_config):
        """Test post_system_test succeeds when no hosts in build mode"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup Foreman mock
            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = []  # No hosts in build mode
            mock_foreman_class.return_value = mock_foreman

            cloud = "cloud01"
            ticket = "TICKET-123"
            hosts = [MockHost("host1.example.com"), MockHost("host2.example.com")]
            report = ""

            result, updated_report = await plugin.post_system_test(cloud, ticket, hosts, report)

            assert result is True

    @pytest.mark.asyncio
    async def test_post_network_test_hosts_down(self, plugin):
        """Test post_network_test detects hosts that are down"""
        with patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class:
            # Setup Netcat mock to return unhealthy for some hosts
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = False
            mock_netcat_class.return_value = mock_nc

            hosts = [
                MockHost("host1.example.com", switch_config_applied=True),
                MockHost("host2.example.com", switch_config_applied=True),
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            plugin.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_post_network_test_missing_switch_config(self, plugin):
        """Test post_network_test detects missing switch configuration"""
        with patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class:
            # Setup Netcat mock
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            # Setup switch dispatcher to return failure
            plugin.switch_dispatcher.verify = AsyncMock(return_value=False)

            # Setup quads API mocks
            current_schedule = MockSchedule()
            plugin.quads.get_current_schedules.return_value = [current_schedule]
            plugin.quads.get_schedules.return_value = []

            hosts = [
                MockHost("host1.example.com", switch_config_applied=False),
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            plugin.logger.error.assert_called()
            # Check that error was logged about missing switch configuration
            error_calls = [str(call) for call in plugin.logger.error.call_args_list]
            assert any("missing switch configuration" in str(call) for call in error_calls)

    @pytest.mark.asyncio
    async def test_post_network_test_ssh_failure(self, plugin):
        """Test post_network_test handles SSH connection failures"""

        # Create a proper exception class
        class SSHHelperException(Exception):
            pass

        with (
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelperException", SSHHelperException),
        ):
            # Setup Netcat mock
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            # Setup SSH to fail with proper exception
            mock_ssh_class.side_effect = SSHHelperException("SSH connection failed")

            hosts = [MockHost("host1.example.com", switch_config_applied=True)]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            assert "Could not establish connection" in updated_report

    @pytest.mark.asyncio
    async def test_post_network_test_switch_config_update(self, plugin):
        """Test post_network_test updates switch config when verified"""
        with (
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            # Setup Netcat mock
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            # Setup switch dispatcher to succeed
            plugin.switch_dispatcher.verify = AsyncMock(return_value=True)

            # Setup SSH mock
            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(return_value=(True, []))
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            # Setup API mocks
            current_schedule = MockSchedule()
            plugin.quads.get_current_schedules.return_value = [current_schedule]
            plugin.quads.get_schedules.return_value = []
            plugin.quads.update_host = MagicMock()

            # Mock gethostbyname
            mock_gethostbyname.return_value = "192.168.1.1"

            hosts = [
                MockHost(
                    "host1.example.com",
                    switch_config_applied=False,
                    interfaces=[MagicMock(name="em1")],
                )
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            # Verify switch config was updated
            plugin.quads.update_host.assert_called_with("host1.example.com", {"switch_config_applied": True})

    @pytest.mark.asyncio
    async def test_validate_success_full_flow(self, plugin, mock_config):
        """Test complete validation flow succeeds"""
        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
            patch("builtins.open", mock_open(read_data="template")),
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup mocks for successful validation
            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = []
            mock_foreman_class.return_value = mock_foreman

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(return_value=(True, []))
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_ipmi_instance = AsyncMock()
            mock_ipmi_instance.enable_user.return_value = True
            mock_ipmi_class.return_value = mock_ipmi_instance

            mock_gethostbyname.return_value = "192.168.1.1"

            # Setup time exceeded
            old_start = datetime.now() - timedelta(minutes=120)
            mock_schedule = MockSchedule(start=old_start)
            plugin.quads.get_current_schedules.return_value = [mock_schedule]

            cloud = "cloud01"
            assignment = MockAssignment()
            hosts = [
                MockHost("host1.example.com", switch_config_applied=True, interfaces=[MagicMock(name="em1")]),
                MockHost("host2.example.com", switch_config_applied=True, interfaces=[MagicMock(name="em1")]),
            ]

            result, report = await plugin.validate(cloud, assignment, hosts, False, False, "")

            assert result is True
            mock_ipmi_instance.enable_user.assert_called()
            plugin.quads.update_notification.assert_called()
            plugin.quads.update_host.assert_called()
            plugin.quads.update_assignment.assert_called()

    @pytest.mark.asyncio
    async def test_validate_within_grace_period(self, plugin):
        """Test validation skipped within grace period"""
        cloud = "cloud01"
        assignment = MockAssignment()
        hosts = [MockHost("host1.example.com")]

        # Setup time within grace period
        recent_start = datetime.now() - timedelta(minutes=30)
        mock_schedule = MockSchedule(start=recent_start)
        plugin.quads.get_current_schedules.return_value = [mock_schedule]

        result, report = await plugin.validate(cloud, assignment, hosts, False, False, "")

        # Validation should be skipped but return success
        assert result is True
        plugin.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_validate_skip_system_tests(self, plugin, mock_config):
        """Test validation with system tests skipped"""
        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
            patch("builtins.open", mock_open(read_data="template")),
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup mocks
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(return_value=(True, []))
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_gethostbyname.return_value = "192.168.1.1"

            # Setup time exceeded
            old_start = datetime.now() - timedelta(minutes=120)
            mock_schedule = MockSchedule(start=old_start)
            plugin.quads.get_current_schedules.return_value = [mock_schedule]

            cloud = "cloud01"
            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com", switch_config_applied=True, interfaces=[MagicMock(name="em1")])]

            # Skip system tests
            result, report = await plugin.validate(cloud, assignment, hosts, skip_system=True, skip_network=False)

            # Should not call post_system_test (no Foreman mock needed)
            assert plugin.logger.info.call_count > 0

    @pytest.mark.asyncio
    async def test_validate_skip_network_tests(self, plugin, mock_config):
        """Test validation with network tests skipped"""
        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper"),
            patch("builtins.open", mock_open(read_data="template")),
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup mocks
            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = []
            mock_foreman_class.return_value = mock_foreman

            mock_ipmi_instance = AsyncMock()
            mock_ipmi_instance.enable_user.return_value = True
            mock_ipmi_class.return_value = mock_ipmi_instance

            # Setup time exceeded
            old_start = datetime.now() - timedelta(minutes=120)
            mock_schedule = MockSchedule(start=old_start)
            plugin.quads.get_current_schedules.return_value = [mock_schedule]

            cloud = "cloud01"
            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            # Skip network tests
            result, report = await plugin.validate(cloud, assignment, hosts, skip_system=False, skip_network=True)

            # Should not call post_network_test
            assert plugin.logger.info.call_count > 0

    @pytest.mark.asyncio
    async def test_validate_notification_on_failure(self, plugin, mock_config):
        """Test validation sends failure notification"""
        # Ensure email_dispatcher.send_mail is async
        plugin.email_dispatcher.send_mail = AsyncMock()

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("builtins.open", mock_open(read_data="template")),
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup to force failure
            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = False  # Force failure
            mock_foreman_class.return_value = mock_foreman

            # Setup time exceeded
            old_start = datetime.now() - timedelta(minutes=120)
            mock_schedule = MockSchedule(start=old_start)
            plugin.quads.get_current_schedules.return_value = [mock_schedule]

            cloud = "cloud01"
            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            result, report = await plugin.validate(cloud, assignment, hosts, False, False, "")

            assert result is False
            # Verify notification was attempted
            plugin.quads.update_notification.assert_called()

    @pytest.mark.asyncio
    async def test_validate_empty_hosts_list(self, plugin):
        """Test validation with no hosts"""
        cloud = "cloud01"
        assignment = MockAssignment()
        hosts = []

        # Setup time exceeded
        old_start = datetime.now() - timedelta(minutes=120)
        mock_schedule = MockSchedule(start=old_start)
        plugin.quads.get_current_schedules.return_value = [mock_schedule]

        result, report = await plugin.validate(cloud, assignment, hosts, False, False, "")

        # Should succeed with no hosts
        assert result is True

    @pytest.mark.asyncio
    async def test_post_network_test_fping_failures(self, plugin, mock_config):
        """Test post_network_test handles fping failures"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup Netcat mock
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            # Setup SSH mock to fail fping
            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(return_value=(False, ["192.168.1.1 is unreachable"]))
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_gethostbyname.return_value = "192.168.1.1"

            hosts = [MockHost("host1.example.com", switch_config_applied=True, interfaces=[MagicMock(name="em1")])]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False

    @pytest.mark.asyncio
    async def test_post_network_test_interface_fping_failures(self, plugin, mock_config):
        """Test post_network_test logs hostname, physical iface, and quads iface"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(
                side_effect=[
                    (True, []),
                    (False, ["172.16.37.26"]),
                    (True, ["enp10s0\n"]),
                ]
            )
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_gethostbyname.return_value = "10.1.37.26"

            iface_em1 = MagicMock()
            iface_em1.name = "em1"
            iface_em2 = MagicMock()
            iface_em2.name = "em2"
            hosts = [
                MockHost(
                    "host1.example.com",
                    switch_config_applied=True,
                    interfaces=[iface_em1, iface_em2],
                )
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            warning_calls = [
                call[0][0] % call[0][1:] if len(call[0]) > 1 else call[0][0]
                for call in plugin.logger.warning.call_args_list
            ]
            assert any("172.16.37.26" in w for w in warning_calls)
            assert any("host1.example.com" in w for w in warning_calls)
            assert any("enp10s0" in w for w in warning_calls)
            assert any("quads: em1" in w for w in warning_calls)

    @pytest.mark.asyncio
    async def test_post_network_test_multi_host_interface_failures(self, plugin, mock_config):
        """Test failure logging distinguishes hosts and interfaces correctly"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(
                side_effect=[
                    (True, []),
                    (False, ["172.16.37.26", "172.16.38.10"]),
                    (True, ["enp10s0\n"]),
                    (True, ["enp10s0\n"]),
                ]
            )
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_gethostbyname.side_effect = lambda name: {
                "host1.example.com": "10.1.37.26",
                "host2.example.com": "10.1.38.10",
            }[name]

            h1_em1 = MagicMock()
            h1_em1.name = "em1"
            h1_em2 = MagicMock()
            h1_em2.name = "em2"
            h2_em1 = MagicMock()
            h2_em1.name = "em1"
            h2_em2 = MagicMock()
            h2_em2.name = "em2"
            hosts = [
                MockHost(
                    "host1.example.com",
                    switch_config_applied=True,
                    interfaces=[h1_em1, h1_em2],
                ),
                MockHost(
                    "host2.example.com",
                    switch_config_applied=True,
                    interfaces=[h2_em1, h2_em2],
                ),
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            warning_calls = [
                call[0][0] % call[0][1:] if len(call[0]) > 1 else call[0][0]
                for call in plugin.logger.warning.call_args_list
            ]
            assert any("host1.example.com" in w and "172.16.37.26" in w for w in warning_calls)
            assert any("host2.example.com" in w and "172.16.38.10" in w for w in warning_calls)
            assert any("quads: em1" in w for w in warning_calls)

    @pytest.mark.asyncio
    async def test_post_network_test_interface_ssh_fallback(self, plugin, mock_config):
        """Test graceful fallback when SSH to failing host fails"""

        class _SSHHelperException(Exception):
            pass

        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch(
                "quads.plugins.builtin.validators.environment.SSHHelperException",
                _SSHHelperException,
            ),
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            fping_ssh = MagicMock()
            fping_ssh.run_cmd = MagicMock(
                side_effect=[
                    (True, []),
                    (False, ["172.16.37.26"]),
                ]
            )
            fping_ssh.disconnect = MagicMock()

            call_count = [0]

            def ssh_factory(hostname, *args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return fping_ssh
                raise _SSHHelperException("Connection refused")

            mock_ssh_class.side_effect = ssh_factory

            mock_gethostbyname.return_value = "10.1.37.26"

            iface_em1 = MagicMock()
            iface_em1.name = "em1"
            iface_em2 = MagicMock()
            iface_em2.name = "em2"
            hosts = [
                MockHost(
                    "host1.example.com",
                    switch_config_applied=True,
                    interfaces=[iface_em1, iface_em2],
                )
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is False
            warning_calls = [
                call[0][0] % call[0][1:] if len(call[0]) > 1 else call[0][0]
                for call in plugin.logger.warning.call_args_list
            ]
            assert any("172.16.37.26" in w for w in warning_calls)
            assert any("host1.example.com" in w for w in warning_calls)
            assert any("no interface ip" in w for w in warning_calls)
            assert any("quads: em1" in w for w in warning_calls)

    @pytest.mark.asyncio
    async def test_post_network_test_resolves_ips_once(self, plugin, mock_config):
        """Test socket.gethostbyname is called once per host, not per interface"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = True
            mock_netcat_class.return_value = mock_nc

            mock_ssh = MagicMock()
            mock_ssh.run_cmd = MagicMock(return_value=(True, []))
            mock_ssh.disconnect = MagicMock()
            mock_ssh_class.return_value = mock_ssh

            mock_gethostbyname.return_value = "10.1.37.26"

            iface_em1 = MagicMock()
            iface_em1.name = "em1"
            iface_em2 = MagicMock()
            iface_em2.name = "em2"
            hosts = [
                MockHost(
                    "host1.example.com",
                    switch_config_applied=True,
                    interfaces=[iface_em1, iface_em2],
                )
            ]
            has_vlan = False
            report = ""

            result, updated_report = await plugin.post_network_test(hosts, has_vlan, report)

            assert result is True
            assert mock_gethostbyname.call_count == 1

    @pytest.mark.asyncio
    async def test_distribute_ssh_keys_success(self, plugin):
        """Test SSH keys are distributed to all hosts"""
        with patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class:
            mock_ssh = MagicMock()
            mock_ssh.distribute_ssh_keys.return_value = True
            mock_ssh_class.return_value = mock_ssh

            plugin.quads.get_ssh_keys_for_assignment.return_value = {
                "keys": ["ssh-rsa AAAA testkey"],
                "usernames": ["testuser"],
            }

            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com"), MockHost("host2.example.com")]

            await plugin._distribute_ssh_keys(assignment, hosts)

            assert mock_ssh_class.call_count == 2
            mock_ssh_class.assert_any_call("host1.example.com")
            mock_ssh_class.assert_any_call("host2.example.com")
            assert mock_ssh.distribute_ssh_keys.call_count == 2
            mock_ssh.distribute_ssh_keys.assert_called_with(["ssh-rsa AAAA testkey"])
            assert mock_ssh.disconnect.call_count == 2

    @pytest.mark.asyncio
    async def test_distribute_ssh_keys_retry_then_succeed(self, plugin):
        """Test SSH key distribution retries on failure and succeeds"""
        from quads.tools.external.ssh_helper import SSHHelperException

        with (
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("quads.plugins.builtin.validators.environment.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_ssh_success = MagicMock()
            mock_ssh_success.distribute_ssh_keys.return_value = True
            mock_ssh_class.side_effect = [
                SSHHelperException("Connection refused"),
                SSHHelperException("Connection refused"),
                mock_ssh_success,
            ]

            plugin.quads.get_ssh_keys_for_assignment.return_value = {
                "keys": ["ssh-rsa AAAA testkey"],
                "usernames": ["testuser"],
            }

            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            await plugin._distribute_ssh_keys(assignment, hosts)

            assert mock_ssh_class.call_count == 3
            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(2)
            mock_ssh_success.distribute_ssh_keys.assert_called_once()
            mock_ssh_success.disconnect.assert_called_once()
            assert plugin.logger.warning.call_count == 2

    @pytest.mark.asyncio
    async def test_distribute_ssh_keys_exhausted_retries(self, plugin):
        """Test SSH key distribution logs warnings but does not fail after exhausting retries"""
        from quads.tools.external.ssh_helper import SSHHelperException

        with (
            patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class,
            patch("quads.plugins.builtin.validators.environment.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_ssh_class.side_effect = SSHHelperException("Connection refused")

            plugin.quads.get_ssh_keys_for_assignment.return_value = {
                "keys": ["ssh-rsa AAAA testkey"],
                "usernames": ["testuser"],
            }

            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            await plugin._distribute_ssh_keys(assignment, hosts)

            assert mock_ssh_class.call_count == 5
            assert plugin.logger.warning.call_count == 5
            last_warning = plugin.logger.warning.call_args[0][0]
            assert "attempt 5/5" in last_warning

    @pytest.mark.asyncio
    async def test_distribute_ssh_keys_no_keys(self, plugin):
        """Test SSH key distribution returns early when no keys exist"""
        with patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class:
            plugin.quads.get_ssh_keys_for_assignment.return_value = {
                "keys": [],
                "usernames": [],
            }

            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            await plugin._distribute_ssh_keys(assignment, hosts)

            mock_ssh_class.assert_not_called()
            plugin.logger.info.assert_called_once()
            assert "No SSH keys" in plugin.logger.info.call_args[0][0]

    @pytest.mark.asyncio
    async def test_distribute_ssh_keys_api_failure(self, plugin):
        """Test SSH key distribution handles API fetch failure gracefully"""
        with patch("quads.plugins.builtin.validators.environment.SSHHelper") as mock_ssh_class:
            plugin.quads.get_ssh_keys_for_assignment.side_effect = Exception("API unreachable")

            assignment = MockAssignment()
            hosts = [MockHost("host1.example.com")]

            await plugin._distribute_ssh_keys(assignment, hosts)

            mock_ssh_class.assert_not_called()
            plugin.logger.warning.assert_called_once()
            assert "Could not fetch SSH keys" in plugin.logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_post_system_test_health_check_failure_skip(self, plugin, mock_config):
        """Test post_system_test skips unhealthy hosts during build"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.Foreman") as mock_foreman_class,
            patch("quads.plugins.builtin.validators.environment.Netcat") as mock_netcat_class,
        ):
            for key, value in mock_config.items():
                setattr(mock_cfg, key, value)

            # Setup Foreman mock
            mock_foreman = AsyncMock()
            mock_foreman.verify_credentials.return_value = True
            mock_foreman.get_build_hosts.return_value = ["host1.example.com"]
            mock_foreman_class.return_value = mock_foreman

            # Setup Netcat mock to fail health check
            mock_nc = AsyncMock()
            mock_nc.health_check.return_value = False
            mock_netcat_class.return_value = mock_nc

            cloud = "cloud01"
            ticket = "TICKET-123"
            hosts = [MockHost("host1.example.com", rack="rack1", uloc="u10", blade="blade1")]
            report = ""

            result, updated_report = await plugin.post_system_test(cloud, ticket, hosts, report)

            assert result is False
            plugin.logger.warning.assert_called()
            assert "didn't pass the health check" in plugin.logger.warning.call_args[0][0]
            # Hardware dispatcher should not be called since health check failed
            plugin.hardware_dispatcher.init.assert_not_called()

    @pytest.mark.asyncio
    async def test_ungate_ipmi_users_success(self, plugin, mock_config):
        """Test _ungate_ipmi_users enables IPMI for all hosts"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class,
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]

            mock_ipmi = AsyncMock()
            mock_ipmi.enable_user = AsyncMock(return_value=True)
            mock_ipmi_class.return_value = mock_ipmi

            hosts = [MockHost("host1.example.com"), MockHost("host2.example.com")]
            await plugin._ungate_ipmi_users(hosts)

            assert mock_ipmi_class.call_count == 2
            assert mock_ipmi.enable_user.call_count == 2
            mock_ipmi.enable_user.assert_called_with(mock_config["ipmi_cloud_username_id"])

    @pytest.mark.asyncio
    async def test_ungate_ipmi_users_partial_failure(self, plugin, mock_config):
        """Test _ungate_ipmi_users logs warning on individual host failure"""
        with (
            patch("quads.plugins.builtin.validators.environment.Config") as mock_cfg,
            patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class,
        ):
            mock_cfg.__getitem__ = lambda self, key: mock_config[key]

            fail_ipmi = AsyncMock()
            fail_ipmi.enable_user = AsyncMock(return_value=False)
            ok_ipmi = AsyncMock()
            ok_ipmi.enable_user = AsyncMock(return_value=True)
            mock_ipmi_class.side_effect = [fail_ipmi, ok_ipmi]

            hosts = [MockHost("host1.example.com"), MockHost("host2.example.com")]
            await plugin._ungate_ipmi_users(hosts)

            plugin.logger.warning.assert_called()
            plugin.logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_ungate_ipmi_users_empty_list(self, plugin, mock_config):
        """Test _ungate_ipmi_users handles empty host list"""
        with patch("quads.plugins.builtin.validators.environment.IPMI") as mock_ipmi_class:
            await plugin._ungate_ipmi_users([])
            mock_ipmi_class.assert_not_called()
