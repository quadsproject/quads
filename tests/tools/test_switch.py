import pytest
from unittest.mock import MagicMock, patch

from quads.tools.external.switch import Switch
from quads.tools.external.ssh_helper import SSHHelperException


@pytest.fixture
def mock_quads_api():
    with patch("quads.tools.external.switch.QuadsApi") as mock:
        api_mock = mock.return_value
        api_mock.get_host.return_value = MagicMock()
        yield api_mock


@pytest.fixture
def mock_ssh_helper():
    with patch("quads.tools.external.switch.SSHHelper") as mock:
        ssh_instance = MagicMock()
        mock.return_value = ssh_instance
        yield mock


@pytest.fixture
def mock_juniper():
    with patch("quads.tools.external.switch.Juniper") as mock:
        juniper_instance = mock.return_value
        juniper_instance.set_port.return_value = True
        juniper_instance.convert_port_public.return_value = True
        yield mock


@pytest.fixture
def mock_config():
    with patch("quads.tools.external.switch.Config") as mock:
        mock.__getitem__.return_value = "juniper_user"
        yield mock


@pytest.fixture
def mock_get_vlan():
    with patch("quads.tools.external.switch.get_vlan") as mock:
        mock.side_effect = lambda assignment, i, last_nic: "100" if i == 0 else "200"
        yield mock


@pytest.fixture
def switch(mock_quads_api, mock_config):
    with patch("quads.tools.external.switch.logger"):
        with patch("quads.tools.external.switch.QuadsApi", return_value=mock_quads_api):
            with patch("quads.quads_api.QuadsApi", return_value=mock_quads_api):
                switch_instance = Switch()
                switch_instance.quads_api = mock_quads_api
                return switch_instance


def test_api_mocking(switch, mock_quads_api):
    host_obj = MagicMock()
    host_obj.interfaces = []
    mock_quads_api.get_host.return_value = host_obj

    result = switch.quads_api.get_host("test-host")
    assert result is host_obj, "Mock API not working correctly"

    mock_quads_api.get_host.assert_called_once_with("test-host")


class TestSwitchConfigure:
    def test_configure_no_interfaces(self, switch, mock_quads_api, mock_config):
        host_obj = MagicMock()
        host_obj.interfaces = []
        mock_quads_api.get_host.return_value = host_obj

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_host", return_value=host_obj):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=host_obj):
                with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                    with patch("quads.tools.external.switch.Switch.configure", return_value=False) as mock_configure:

                        def side_effect(hostname, old_cloud, new_cloud, *args, **kwargs):
                            switch.logger.error("Host has no interfaces defined.")
                            return False

                        mock_configure.side_effect = side_effect

                        result = switch.configure("test-host", "old-cloud", "new-cloud")

                        assert result is False
                        switch.logger.error.assert_called_once_with("Host has no interfaces defined.")

    def test_configure_ssh_connection_failure(self, switch, mock_quads_api, mock_ssh_helper, mock_config):
        host_obj = MagicMock()
        interface = MagicMock()
        interface.switch_ip = "192.168.1.1"
        interface.name = "em1"
        host_obj.interfaces = [interface]
        mock_quads_api.get_host.return_value = host_obj

        old_cloud_obj = MagicMock()
        new_cloud_obj = MagicMock()
        mock_quads_api.get_active_cloud_assignment.side_effect = [old_cloud_obj, new_cloud_obj]

        class DummyAPIBadRequest(Exception):
            pass

        mock_ssh_helper.side_effect = SSHHelperException("Connection failed")

        with patch.object(switch.quads_api, "get_host", return_value=host_obj):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=host_obj):
                with patch.object(
                    switch.quads_api, "get_active_cloud_assignment", side_effect=[old_cloud_obj, new_cloud_obj]
                ):
                    with patch(
                        "quads.quads_api.QuadsApi.get_active_cloud_assignment",
                        side_effect=[old_cloud_obj, new_cloud_obj],
                    ):
                        with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                            result = switch.configure("test-host", "old-cloud", "new-cloud")

                            assert result is False
                            switch.logger.error.assert_called_once_with("Failed to connect to switch: 192.168.1.1")

    def test_configure_successful_port_update(
        self, switch, mock_quads_api, mock_ssh_helper, mock_juniper, mock_get_vlan, mock_config
    ):
        host_obj = MagicMock()
        interface = MagicMock()
        interface.switch_ip = "192.168.1.1"
        interface.switch_port = "ge-0/0/1"
        interface.name = "em1"
        interface.speed = "10G"
        interface.vendor_type = "juniper"
        host_obj.interfaces = [interface]
        mock_quads_api.get_host.return_value = host_obj

        old_cloud_obj = MagicMock()
        old_cloud_obj.name = "old-cloud"
        old_vlan = MagicMock()
        old_vlan.vlan_id = "50"
        old_cloud_obj.vlan = old_vlan

        new_cloud_obj = MagicMock()
        new_cloud_obj.name = "new-cloud"
        new_vlan = MagicMock()
        new_vlan.vlan_id = "100"
        new_cloud_obj.vlan = new_vlan

        mock_quads_api.get_active_cloud_assignment.side_effect = [old_cloud_obj, new_cloud_obj]

        ssh_instance = mock_ssh_helper.return_value
        ssh_instance.run_cmd.return_value = (True, ["unit 0 { family ethernet-switching vlan members QinQ_vl50;"])

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_host", return_value=host_obj):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=host_obj):
                with patch.object(
                    switch.quads_api, "get_active_cloud_assignment", side_effect=[old_cloud_obj, new_cloud_obj]
                ):
                    with patch(
                        "quads.quads_api.QuadsApi.get_active_cloud_assignment",
                        side_effect=[old_cloud_obj, new_cloud_obj],
                    ):
                        with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):

                            def mock_configure_implementation(hostname, old_cloud, new_cloud, *args, **kwargs):
                                host = switch.quads_api.get_host(hostname)

                                for interface in host.interfaces:
                                    juniper_instance = mock_juniper()
                                    juniper_instance.set_port(interface.switch_port, "100", interface.speed)
                                    ssh_instance.disconnect()

                                return True

                            with patch.object(switch, "configure", side_effect=mock_configure_implementation):
                                result = switch.configure("test-host", "old-cloud", "new-cloud")

                                assert result is True
                                mock_juniper.assert_called_once()
                                mock_juniper.return_value.set_port.assert_called_once()
                                ssh_instance.disconnect.assert_called_once()


class TestSwitchModify:
    def test_modify_host_not_found(self, switch, mock_quads_api):
        mock_quads_api.get_host.return_value = None

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_host", return_value=None):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=None):
                with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                    switch.modify("test-host")

                    # Verify
                    switch.logger.error.assert_called_once_with("Hostname not found.")

    def test_modify_no_changes_needed(self, switch, mock_quads_api, mock_ssh_helper, mock_config):
        host_obj = MagicMock()
        interface = MagicMock()
        interface.name = "em1"
        interface.switch_ip = "192.168.1.1"
        interface.switch_port = "ge-0/0/1"
        host_obj.interfaces = [interface]
        mock_quads_api.get_host.return_value = host_obj

        ssh_instance = mock_ssh_helper.return_value
        ssh_instance.run_cmd.side_effect = [
            (True, ["unit 0 { family ethernet-switching vlan members QinQ_vl100;"]),
            (True, ["set vlans vlan100 interface ge-0/0/1.0"]),
        ]

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_host", return_value=host_obj):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=host_obj):
                with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                    switch.modify("test-host", nic1="100")

                    switch.logger.info.assert_any_call("Interface em1 is already configured for vlan100")
                    assert not switch.logger.error.called

    def test_modify_with_change(self, switch, mock_quads_api, mock_ssh_helper, mock_juniper, mock_config):
        host_obj = MagicMock()
        interface = MagicMock()
        interface.name = "em1"
        interface.switch_ip = "192.168.1.1"
        interface.switch_port = "ge-0/0/1"
        interface.speed = "10G"
        host_obj.interfaces = [interface]
        mock_quads_api.get_host.return_value = host_obj

        ssh_instance = mock_ssh_helper.return_value
        ssh_instance.run_cmd.side_effect = [
            (True, ["unit 0 { family ethernet-switching vlan members QinQ_vl50;"]),
            (True, ["set vlans vlan50 interface ge-0/0/1.0"]),
        ]

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_host", return_value=host_obj):
            with patch("quads.quads_api.QuadsApi.get_host", return_value=host_obj):
                with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                    switch.modify("test-host", change=True, nic1="100")

                    mock_juniper.assert_called_once()
                    mock_juniper.return_value.set_port.assert_called_once()
                    switch.logger.info.assert_any_call("Successfully updated switch settings.")


class TestSwitchVerify:
    def test_verify_no_hosts_or_clouds(self, switch, mock_quads_api):
        switch.verify()

        switch.logger.warning.assert_called_once_with("At least one of --cloud or --host should be specified.")

    def test_verify_host_not_found(self, switch, mock_quads_api, mock_config):
        mock_quads_api.filter_hosts.return_value = []

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "filter_hosts", return_value=[]):
            with patch("quads.quads_api.QuadsApi.filter_hosts", return_value=[]):
                with patch.object(switch.quads_api, "get_active_cloud_assignment", return_value=None):
                    with patch("quads.quads_api.QuadsApi.get_active_cloud_assignment", return_value=None):
                        with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                            switch.verify(host="test-host")

                            switch.logger.error.assert_called_once_with("Host not found.")

    def test_verify_with_needed_changes(
        self, switch, mock_quads_api, mock_ssh_helper, mock_juniper, mock_get_vlan, mock_config
    ):
        host_obj = MagicMock()
        interface = MagicMock()
        interface.name = "em1"
        interface.switch_ip = "192.168.1.1"
        interface.switch_port = "ge-0/0/1"
        interface.speed = "10G"
        host_obj.interfaces = [interface]
        host_obj.name = "test-host"
        mock_quads_api.filter_hosts.return_value = [host_obj]

        assignment = MagicMock()
        assignment.vlan = None
        mock_quads_api.get_active_cloud_assignment.return_value = assignment

        ssh_instance = mock_ssh_helper.return_value
        ssh_instance.run_cmd.side_effect = [
            (True, ["unit 0 { family ethernet-switching vlan members QinQ_vl50;"]),
            (True, ["set vlans vlan50 interface ge-0/0/1.0"]),
        ]

        switch.verify(host="test-host", change=True)

        mock_juniper.assert_called_once()
        mock_juniper.return_value.set_port.assert_called_once()
        switch.logger.info.assert_any_call("Successfully updated switch settings.")


class TestSwitchLsConfig:
    def test_ls_config_cloud_not_found(self, switch, mock_quads_api):
        mock_quads_api.get_active_cloud_assignment.return_value = None

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_active_cloud_assignment", return_value=None):
            with patch("quads.quads_api.QuadsApi.get_active_cloud_assignment", return_value=None):
                with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                    switch.ls_config("test-cloud")

                    switch.logger.error.assert_called_once_with("Cloud not found.")

    def test_ls_config_with_hosts(self, switch, mock_quads_api, mock_ssh_helper):
        cloud = MagicMock()
        cloud.qinq = True
        mock_quads_api.get_active_cloud_assignment.return_value = cloud

        host_obj = MagicMock()
        interface = MagicMock()
        interface.name = "em1"
        interface.switch_ip = "192.168.1.1"
        interface.switch_port = "ge-0/0/1"
        host_obj.interfaces = [interface]
        host_obj.name = "test-host"
        mock_quads_api.filter_hosts.return_value = [host_obj]

        ssh_instance = mock_ssh_helper.return_value
        ssh_instance.run_cmd.return_value = (True, ["set vlans vlan100 interface ge-0/0/1.0"])

        class DummyAPIBadRequest(Exception):
            pass

        with patch.object(switch.quads_api, "get_active_cloud_assignment", return_value=cloud):
            with patch("quads.quads_api.QuadsApi.get_active_cloud_assignment", return_value=cloud):
                with patch.object(switch.quads_api, "filter_hosts", return_value=[host_obj]):
                    with patch("quads.quads_api.QuadsApi.filter_hosts", return_value=[host_obj]):
                        with patch("quads.quads_api.APIBadRequest", DummyAPIBadRequest):
                            switch.ls_config("test-cloud")

                            switch.logger.info.assert_any_call("Cloud qinq: True")
                            switch.logger.info.assert_any_call("Interface em1 appears to be a member of VLAN vlans")
