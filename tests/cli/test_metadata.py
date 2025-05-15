import os.path
from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.models import db
from tests.cli.config import CLOUD, HOST_TYPE, MODEL1
from tests.cli.test_base import TestBase


def finalizer():
    host_import = HostDao.get_host("imported.example.com")
    cloud_import = CloudDao.get_cloud("cloud42")

    if host_import:
        HostDao.remove_host(name="imported.example.com")

    if cloud_import:
        CloudDao.remove_cloud("cloud42")


@pytest.fixture
def define_fixture(request):
    request.addfinalizer(finalizer)

    CloudDao.create_cloud("cloud42")
    HostDao.create_host("imported.example.com", MODEL1, HOST_TYPE, CLOUD)


class TestExport(TestBase):
    def test_export(self, define_fixture):

        self.quads_cli_call("host_metadata_export")

        assert self._caplog.messages[0].startswith("Metadata successfully exported to ")
        filename = self._caplog.messages[0].split()[-1][:-1]
        assert os.path.exists(filename)
        with open(filename, "r+") as f:
            d = f.readlines()
            f.seek(0)
            for i in d:
                if not i.startswith("  created_at: "):
                    f.write(i)
            f.truncate()

        assert list(open(filename)) == list(open(os.path.join(os.path.dirname(__file__), "fixtures/metadata")))


class TestImport(TestBase):
    def test_import(self, define_fixture):
        self.cli_args["metadata"] = os.path.join(os.path.dirname(__file__), "fixtures/metadata_import.yaml")

        self.quads_cli_call("define_host_metadata")

        assert self._caplog.messages[0] == (
            "imported.example.com [RECREATING]: ['broken', 'disks', 'host_type', "
            "'interfaces', 'memory', 'model', 'retired']"
        )
        host = HostDao.get_host("imported.example.com")
        db.session.refresh(host)
        assert host.broken
        assert host.retired
        assert host.default_cloud.name == "cloud42"
        assert host.host_type == "imported"
        assert host.model == "IMPORTED"
        assert host.disks[0].disk_type == "NVME"
        assert host.disks[0].size_gb == 4096
        assert host.disks[0].count == 10
        assert host.disks[1].disk_type == "SATA"
        assert host.disks[1].size_gb == 4096
        assert host.disks[1].count == 5
        assert host.memory[0].handle == "DIMM1"
        assert host.memory[0].size_gb == 4096
        assert host.interfaces[0].name == "em1"
        assert host.interfaces[0].bios_id == "NIC.Intel.1"
        assert host.interfaces[0].mac_address == "A0:B1:C2:D3:E4:F5"
        assert not host.interfaces[0].maintenance
        assert host.interfaces[0].switch_ip == "10.0.0.1"
        assert host.interfaces[0].switch_port == "et-4:0/0"
        assert host.interfaces[0].speed == 1000
        assert host.interfaces[0].vendor == "Intel"

    def test_import_no_arg(self, define_fixture):
        self.cli_args["metadata"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("define_host_metadata")
        assert str(ex.value) == "Missing option --metadata"

    def test_import_bad_host(self, define_fixture):
        self.cli_args["force"] = False
        self.cli_args["metadata"] = os.path.join(os.path.dirname(__file__), "fixtures/badhost_metadata_import.yaml")

        self.quads_cli_call("define_host_metadata")
        assert self._caplog.messages[0] == "Host badhost.example.com not found. Skipping."
        assert self._caplog.messages[1] == "For overwriting existing values use the --force."

    def test_import_bad_path(self, define_fixture):
        self.cli_args["metadata"] = "this/path/should/never/exist.exe"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("define_host_metadata")
        assert str(ex.value) == "The path for the --metadata yaml is not valid"

    @patch("quads.cli.cli.open")
    def test_import_io_error(self, mock_load, define_fixture):
        mock_load.side_effect = IOError("IOError")
        self.cli_args["metadata"] = os.path.join(os.path.dirname(__file__), "fixtures/metadata_import.yaml")

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("define_host_metadata")
        assert str(ex.value) == f"There was something wrong reading from {self.cli_args['metadata']}"
