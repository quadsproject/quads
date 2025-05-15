from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.quads_api import APIServerException
from quads.server.dao.host import HostDao
from quads.server.dao.interface import InterfaceDao
from quads.server.models import db
from tests.cli.config import (
    HOST1,
    HOST2,
    IFBIOSID1,
    IFBIOSID2,
    IFIP1,
    IFIP2,
    IFMAC1,
    IFMAC2,
    IFNAME1,
    IFNAME2,
    IFPORT1,
    IFPORT2,
    IFSPEED,
    IFVENDOR1,
    IFVENDOR2,
)
from tests.cli.test_base import TestBase


def finalizer():
    host = HostDao.get_host(HOST2)
    if host:
        for interface in host.interfaces:
            InterfaceDao.delete_interface(interface.id)


@pytest.fixture
def remove_interface(request):
    request.addfinalizer(finalizer)


@pytest.fixture
def mod_interface(request):
    request.addfinalizer(finalizer)
    InterfaceDao.create_interface(
        HOST2,
        IFNAME2,
        IFBIOSID2,
        IFMAC2,
        IFIP2,
        IFPORT2,
        IFSPEED,
        IFVENDOR2,
        False,
        False,
    )


class TestInterface(TestBase):
    def test_define_interface_no_params(self):
        try:
            self.quads_cli_call("addinterface")
        except CliException as ex:
            assert str(ex) == (
                "Missing option. All these options are required for --add-interface:\n"
                "\t--host\n"
                "\t--interface-name\n"
                "\t--interface-mac\n"
                "\t--interface-ip\n"
                "\t--interface-port"
            )

    def test_define_interface(self, remove_interface):
        self.cli_args["host"] = HOST2
        self.cli_args["ifname"] = IFNAME2
        self.cli_args["ifmac"] = IFMAC2
        self.cli_args["ifip"] = IFIP2
        self.cli_args["ifport"] = IFPORT2
        self.cli_args["ifbiosid"] = IFBIOSID2
        self.cli_args["ifspeed"] = IFSPEED
        self.cli_args["ifvendor"] = IFVENDOR2

        self.quads_cli_call("addinterface")

        host = HostDao.get_host(HOST2)
        assert host.interfaces[0].name == IFNAME2
        assert host.interfaces[0].mac_address == IFMAC2
        assert host.interfaces[0].switch_ip == IFIP2
        assert host.interfaces[0].switch_port == IFPORT2
        assert host.interfaces[0].bios_id == IFBIOSID2
        assert host.interfaces[0].speed == IFSPEED
        assert host.interfaces[0].vendor == IFVENDOR2
        assert host.interfaces[0].pxe_boot
        assert not host.interfaces[0].maintenance

    def test_mod_interface(self, mod_interface):
        self.cli_args["host"] = HOST2
        self.cli_args["ifname"] = IFNAME2
        self.cli_args["ifip"] = "192.168.0.1"

        self.quads_cli_call("modinterface")

        host = HostDao.get_host(HOST2)
        assert len(host.interfaces) == 1
        assert host.interfaces[0].name == IFNAME2
        assert host.interfaces[0].switch_ip == "192.168.0.1"

    def test_mod_interface_no_arg(self, mod_interface):
        self.cli_args["host"] = HOST2
        self.cli_args["ifname"] = IFNAME2
        self.cli_args["ifmac"] = None
        self.cli_args["ifip"] = None
        self.cli_args["ifport"] = None
        self.cli_args["ifbiosid"] = None
        self.cli_args["ifspeed"] = None
        self.cli_args["ifvendor"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modinterface")

        assert str(ex.value) == (
            "Missing options. At least one of these options are required for "
            "--mod-interface:\n"
            "\t--interface-name\n"
            "\t--interface-bios-id\n"
            "\t--interface-mac\n"
            "\t--interface-ip\n"
            "\t--interface-port\n"
            "\t--interface-speed\n"
            "\t--interface-vendor\n"
            "\t--pxe-boot\n"
            "\t--maintenance"
        )

    def test_mod_interface_no_host(self, mod_interface):
        self.cli_args["host"] = None
        self.cli_args["ifname"] = IFNAME2
        self.cli_args["ifip"] = "192.168.0.1"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modinterface")

        assert str(ex.value) == "Missing option. --host and --interface-name options are required for --mod-interface:"

    def test_mod_interface_bad_host(self, mod_interface):
        self.cli_args["host"] = "BADHOST"
        self.cli_args["ifname"] = IFNAME2
        self.cli_args["ifip"] = "192.168.0.1"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modinterface")

        assert str(ex.value) == "Host not found: BADHOST"

    def test_rm_interface(self, mod_interface):
        self.cli_args["host"] = HOST2
        self.cli_args["ifname"] = IFNAME2

        self.quads_cli_call("rminterface")

        host = HostDao.get_host(HOST2)
        db.session.refresh(host)
        assert len(host.interfaces) == 0

    def test_rm_interface_no_host(self, mod_interface):
        self.cli_args["host"] = None
        self.cli_args["ifname"] = IFNAME2

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rminterface")

        assert str(ex.value) == "Missing option. --host and --interface-name options are required for --rm-interface"

    @patch("quads.quads_api.QuadsApi.remove_interface")
    def test_rm_interface_exception(self, mock_remove, mod_interface):
        mock_remove.side_effect = APIServerException("Connection Error")
        self.cli_args["host"] = HOST2
        self.cli_args["ifname"] = IFNAME2

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rminterface")

        assert str(ex.value) == "Connection Error"

    def test_rm_interface_bad_host(self, mod_interface):
        self.cli_args["host"] = "BADHOST"
        self.cli_args["ifname"] = IFNAME2

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rminterface")

        assert str(ex.value) == "Host not found: BADHOST"

    def test_ls_interface(self):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("interface")

        assert self._caplog.messages[0] == f"interface: {IFNAME1}"
        assert self._caplog.messages[1] == f"  bios id: {IFBIOSID1}"
        assert self._caplog.messages[2] == f"  mac address: {IFMAC1}"
        assert self._caplog.messages[3] == f"  switch ip: {IFIP1}"
        assert self._caplog.messages[4] == f"  port: {IFPORT1}"
        assert self._caplog.messages[5] == f"  speed: {IFSPEED}"
        assert self._caplog.messages[6] == f"  vendor: {IFVENDOR1}"
        assert self._caplog.messages[7] == "  pxe_boot: True"
        assert self._caplog.messages[8] == "  maintenance: False"

    def test_ls_interface_missing_host(self):
        if self.cli_args.get("host"):
            self.cli_args.pop("host")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("interface")
        assert str(ex.value) == "Missing option. --host option is required for --ls-interface."

    def test_ls_interface_bad_host(self):
        self.cli_args["host"] = "BADHOST"
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("interface")
        assert str(ex.value) == "Host not found: BADHOST"

    def test_ls_interface_noiface_host(self):
        self.cli_args["host"] = HOST2
        self.quads_cli_call("interface")
        assert self._caplog.messages[0] == f"No interfaces defined for {HOST2}"
