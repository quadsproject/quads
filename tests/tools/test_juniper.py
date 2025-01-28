from unittest.mock import patch, AsyncMock, Mock

import pexpect
import pytest

from quads.tools.external.juniper import Juniper, JuniperException


class TestJuniper(object):

    ip_address = "10.0.0.6"
    switch_port = "10.0.0.2"
    port_speed = "1"
    old_vlan = "10.0.0.3"
    new_vlan = "10.0.0.4"

    def test_object_parameters(self):
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        assert juniper.ip_address == self.ip_address

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_close(self, mock_spawn):
        mock_spawn.return_value.__aenter__.return_value = Mock()
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        juniper.connect()
        juniper.close()
        juniper.child = None
        assert not juniper.child

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_connect(self, mock_spawn):
        mock_spawn.return_value.__aenter__.return_value = Mock()
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        juniper.connect()
        assert juniper.child

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_connect_exception(self, mock_spawn):
        mock_spawn.side_effect = pexpect.exceptions.TIMEOUT("Timeout")
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        with pytest.raises(JuniperException):
            juniper.connect()
            assert not juniper.child

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_execute(self, mock_spawn):
        mock_spawn.return_value.__aenter__.return_value = Mock()
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        juniper.connect()
        juniper.execute(command="ls")
        assert juniper.child

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_set_port(self, mock_spawn):
        mock_spawn.side_effect = Mock()
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, None, self.new_vlan)
        response = juniper.set_port()
        assert response

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_set_port_exception(self, mock_spawn):
        mock_spawn.side_effect = pexpect.exceptions.TIMEOUT("Timeout")
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        response = juniper.set_port()
        assert not response

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_set_port_old_vlan(self, mock_spawn):
        mock_spawn.side_effect = Mock()
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        response = juniper.set_port()
        assert response

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_convert_port_public(self, mock_spawn):
        mock_spawn.side_effect = Mock()
        juniper = Juniper(
            ip_address=self.ip_address,
            switch_port=self.switch_port,
            port_speed=self.port_speed,
            old_vlan=None,
            new_vlan=self.new_vlan,
        )
        response = juniper.convert_port_public()
        assert response

    @patch("quads.tools.external.juniper.pexpect.spawn")
    def test_convert_port_public_exception(self, mock_spawn):
        mock_spawn.side_effect = pexpect.exceptions.TIMEOUT("Timeout")
        juniper = Juniper(self.ip_address, self.switch_port, self.port_speed, self.old_vlan, self.new_vlan)
        response = juniper.convert_port_public()
        assert not response
