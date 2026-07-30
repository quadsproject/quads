from unittest.mock import MagicMock, Mock, patch

import pexpect
import pytest

from quads.tools.external.juniper_roce import (
    BASE_CONFIG_COMMANDS,
    BASE_CONFIG_DELETE_COMMANDS,
    INTERFACE_CONFIG_DELETE_TEMPLATE,
    INTERFACE_CONFIG_TEMPLATE,
    JuniperRoCE,
    JuniperRoCEException,
)


class TestJuniperRoCE:
    ip_address = "10.0.0.1"

    def test_object_parameters(self):
        juniper = JuniperRoCE(self.ip_address)
        assert juniper.ip_address == self.ip_address
        assert juniper.child is None

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_connect(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        assert juniper.child is not None

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_connect_timeout(self, mock_spawn):
        mock_spawn.side_effect = pexpect.exceptions.TIMEOUT("Timeout")
        juniper = JuniperRoCE(self.ip_address)
        with pytest.raises(JuniperRoCEException):
            juniper.connect()

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_execute(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        juniper.execute(command="show version")
        juniper.child.sendline.assert_called_with("show version")

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_execute_timeout(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        juniper.child.expect.side_effect = pexpect.exceptions.TIMEOUT("Timeout")
        with pytest.raises(JuniperRoCEException):
            juniper.execute(command="show version")

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_close(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        juniper.close()
        juniper.child.close.assert_called_once()

    def test_close_no_child(self):
        juniper = JuniperRoCE(self.ip_address)
        juniper.close()

    @patch("quads.tools.external.juniper_roce.SSHHelper")
    def test_has_base_config_true(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (
            True,
            ["set class-of-service classifiers dscp STORAGE-CLASSIFIER\n"],
        )
        mock_ssh_cls.return_value = mock_ssh
        juniper = JuniperRoCE(self.ip_address)
        assert juniper.has_base_config() is True
        mock_ssh.disconnect.assert_called_once()

    @patch("quads.tools.external.juniper_roce.SSHHelper")
    def test_has_base_config_false(self, mock_ssh_cls):
        mock_ssh = MagicMock()
        mock_ssh.run_cmd.return_value = (True, [])
        mock_ssh_cls.return_value = mock_ssh
        juniper = JuniperRoCE(self.ip_address)
        assert juniper.has_base_config() is False

    @patch("quads.tools.external.juniper_roce.SSHHelper")
    def test_has_base_config_ssh_failure(self, mock_ssh_cls):
        from quads.tools.external.ssh_helper import SSHHelperException

        mock_ssh_cls.side_effect = SSHHelperException("Connection failed")
        juniper = JuniperRoCE(self.ip_address)
        assert juniper.has_base_config() is False

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_apply_base_config_success(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        assert juniper.apply_base_config() is True
        sent = [c.args[0] for c in juniper.child.sendline.call_args_list]
        for cmd in BASE_CONFIG_COMMANDS:
            assert cmd in sent

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_apply_base_config_failure(self, mock_spawn):
        mock_child = Mock()
        mock_spawn.return_value = mock_child
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        call_count = 0
        total_before_commit = 2 + len(BASE_CONFIG_COMMANDS)

        def side_effect(pattern, timeout=120):
            nonlocal call_count
            call_count += 1
            if call_count > total_before_commit:
                raise pexpect.exceptions.TIMEOUT("Timeout on commit")

        mock_child.expect.side_effect = side_effect
        assert juniper.apply_base_config() is False

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_apply_interface_config_success(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        assert juniper.apply_interface_config("et-0/0/7:1") is True
        sent = [c.args[0] for c in juniper.child.sendline.call_args_list]
        for template in INTERFACE_CONFIG_TEMPLATE:
            assert template.format(switch_port="et-0/0/7:1") in sent

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_apply_interface_config_failure(self, mock_spawn):
        mock_child = Mock()
        mock_spawn.return_value = mock_child
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        call_count = 0

        def side_effect(pattern, timeout=120):
            nonlocal call_count
            call_count += 1
            if call_count > 2 + len(INTERFACE_CONFIG_TEMPLATE):
                raise pexpect.exceptions.TIMEOUT("Timeout on commit")

        mock_child.expect.side_effect = side_effect
        assert juniper.apply_interface_config("et-0/0/7:1") is False

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_remove_base_config_success(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        assert juniper.remove_base_config() is True
        sent = [c.args[0] for c in juniper.child.sendline.call_args_list]
        for cmd in BASE_CONFIG_DELETE_COMMANDS:
            assert cmd in sent

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_remove_base_config_failure(self, mock_spawn):
        mock_child = Mock()
        mock_spawn.return_value = mock_child
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        call_count = 0
        total_before_commit = 2 + len(BASE_CONFIG_DELETE_COMMANDS)

        def side_effect(pattern, timeout=120):
            nonlocal call_count
            call_count += 1
            if call_count > total_before_commit:
                raise pexpect.exceptions.TIMEOUT("Timeout on commit")

        mock_child.expect.side_effect = side_effect
        assert juniper.remove_base_config() is False

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_remove_interface_config_success(self, mock_spawn):
        mock_spawn.return_value = Mock()
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        assert juniper.remove_interface_config("et-0/0/7:1") is True
        sent = [c.args[0] for c in juniper.child.sendline.call_args_list]
        for template in INTERFACE_CONFIG_DELETE_TEMPLATE:
            assert template.format(switch_port="et-0/0/7:1") in sent

    @patch("quads.tools.external.juniper_roce.pexpect.spawn")
    def test_remove_interface_config_failure(self, mock_spawn):
        mock_child = Mock()
        mock_spawn.return_value = mock_child
        juniper = JuniperRoCE(self.ip_address)
        juniper.connect()
        call_count = 0

        def side_effect(pattern, timeout=120):
            nonlocal call_count
            call_count += 1
            if call_count > 2 + len(INTERFACE_CONFIG_DELETE_TEMPLATE):
                raise pexpect.exceptions.TIMEOUT("Timeout on commit")

        mock_child.expect.side_effect = side_effect
        assert juniper.remove_interface_config("et-0/0/7:1") is False


class TestRoCEConfigurator:
    @staticmethod
    def _make_interface(name, switch_ip, switch_port):
        iface = MagicMock()
        iface.name = name
        iface.switch_ip = switch_ip
        iface.switch_port = switch_port
        return iface

    @staticmethod
    def _make_host(name, interfaces):
        host = MagicMock()
        host.name = name
        host.interfaces = interfaces
        return host

    # --install-roce tests (uses --switch / --sw-list)

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_single_switch(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = False
        mock_instance.apply_base_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1"])
        assert configurator.run() is True
        mock_juniper_cls.assert_called_once_with("10.0.0.1")
        mock_instance.apply_base_config.assert_called_once()

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_multiple_switches(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = False
        mock_instance.apply_base_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1", "10.0.0.2"])
        assert configurator.run() is True
        assert mock_juniper_cls.call_count == 2
        assert mock_instance.apply_base_config.call_count == 2

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_skips_existing(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1"])
        assert configurator.run() is True
        mock_instance.apply_base_config.assert_not_called()

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_dry_run(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1"], dry_run=True)
        assert configurator.run() is True
        mock_juniper_cls.assert_not_called()

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_connection_failure(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.connect.side_effect = JuniperRoCEException("Fail")
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    def test_install_roce_apply_failure(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = False
        mock_instance.apply_base_config.return_value = False
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("install_roce", switches=["10.0.0.1"])
        assert configurator.run() is False

    # --uninstall-roce tests (uses --switch / --sw-list)

    @patch("quads.tools.roce.JuniperRoCE")
    def test_uninstall_roce_removes_base(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = True
        mock_instance.remove_base_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("uninstall_roce", switches=["10.0.0.1"])
        assert configurator.run() is True
        mock_instance.remove_base_config.assert_called_once()

    @patch("quads.tools.roce.JuniperRoCE")
    def test_uninstall_roce_skips_missing(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = False
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("uninstall_roce", switches=["10.0.0.1"])
        assert configurator.run() is True
        mock_instance.remove_base_config.assert_not_called()

    @patch("quads.tools.roce.JuniperRoCE")
    def test_uninstall_roce_connection_failure(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.connect.side_effect = JuniperRoCEException("Fail")
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("uninstall_roce", switches=["10.0.0.1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    def test_uninstall_roce_remove_failure(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = True
        mock_instance.remove_base_config.return_value = False
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("uninstall_roce", switches=["10.0.0.1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    def test_uninstall_roce_dry_run(self, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        configurator = RoCEConfigurator("uninstall_roce", switches=["10.0.0.1"], dry_run=True)
        assert configurator.run() is True
        mock_juniper_cls.assert_not_called()

    # --configure tests (uses --host + --interfaces)

    @patch("quads.tools.roce.quads")
    def test_configure_host_not_found(self, mock_quads):
        from quads.tools.roce import RoCEConfigurator

        mock_quads.get_host.return_value = None
        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.quads")
    def test_configure_host_no_interfaces(self, mock_quads):
        from quads.tools.roce import RoCEConfigurator

        mock_quads.get_host.return_value = self._make_host("host01", [])
        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.quads")
    def test_configure_interface_not_found(self, mock_quads):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])
        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1", "em99"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_configure_errors_without_base(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = False
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1"])
        assert configurator.run() is False
        mock_instance.apply_interface_config.assert_not_called()

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_configure_applies_selected_interfaces(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface1 = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        iface2 = self._make_interface("em2", "10.0.0.1", "et-0/0/1:1")
        iface3 = self._make_interface("em3", "10.0.0.1", "et-0/0/1:2")
        mock_quads.get_host.return_value = self._make_host("host01", [iface1, iface2, iface3])

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = True
        mock_instance.apply_interface_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1", "em3"])
        assert configurator.run() is True
        assert mock_instance.apply_interface_config.call_count == 2

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_configure_interface_failure_continues(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface1 = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        iface2 = self._make_interface("em2", "10.0.0.1", "et-0/0/1:1")
        mock_quads.get_host.return_value = self._make_host("host01", [iface1, iface2])

        mock_instance = MagicMock()
        mock_instance.has_base_config.return_value = True
        mock_instance.apply_interface_config.side_effect = [False, True]
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1", "em2"])
        assert configurator.run() is False
        assert mock_instance.apply_interface_config.call_count == 2

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_configure_connection_failure(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])

        mock_instance = MagicMock()
        mock_instance.connect.side_effect = JuniperRoCEException("Fail")
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_configure_dry_run(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])

        configurator = RoCEConfigurator("configure", host="host01", interfaces=["em1"], dry_run=True)
        assert configurator.run() is True
        mock_juniper_cls.assert_not_called()

    # --remove tests (uses --host + --interfaces)

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_remove_removes_selected_interfaces(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface1 = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        iface2 = self._make_interface("em2", "10.0.0.1", "et-0/0/1:1")
        mock_quads.get_host.return_value = self._make_host("host01", [iface1, iface2])

        mock_instance = MagicMock()
        mock_instance.remove_interface_config.return_value = True
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("remove", host="host01", interfaces=["em1"])
        assert configurator.run() is True
        mock_instance.remove_interface_config.assert_called_once()

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_remove_connection_failure(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])

        mock_instance = MagicMock()
        mock_instance.connect.side_effect = JuniperRoCEException("Fail")
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("remove", host="host01", interfaces=["em1"])
        assert configurator.run() is False

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_remove_interface_failure_continues(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface1 = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        iface2 = self._make_interface("em2", "10.0.0.1", "et-0/0/1:1")
        mock_quads.get_host.return_value = self._make_host("host01", [iface1, iface2])

        mock_instance = MagicMock()
        mock_instance.remove_interface_config.side_effect = [False, True]
        mock_juniper_cls.return_value = mock_instance

        configurator = RoCEConfigurator("remove", host="host01", interfaces=["em1", "em2"])
        assert configurator.run() is False
        assert mock_instance.remove_interface_config.call_count == 2

    @patch("quads.tools.roce.JuniperRoCE")
    @patch("quads.tools.roce.quads")
    def test_remove_dry_run(self, mock_quads, mock_juniper_cls):
        from quads.tools.roce import RoCEConfigurator

        iface = self._make_interface("em1", "10.0.0.1", "et-0/0/1:0")
        mock_quads.get_host.return_value = self._make_host("host01", [iface])

        configurator = RoCEConfigurator("remove", host="host01", interfaces=["em1"], dry_run=True)
        assert configurator.run() is True
        mock_juniper_cls.assert_not_called()
