import pytest

from quads.exceptions import CliException
from tests.cli.config import HOST1, HOST2
from tests.cli.test_base import TestBase


class TestDisk(TestBase):
    def test_ls_disk(self, capsys):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("disks")
        output = capsys.readouterr().out

        assert "Disks:" in output
        assert "NVME" in output
        assert "4096" in output
        assert "10" in output
        assert "SATA" in output
        assert "5" in output

    def test_ls_disk_missing_host(self):
        if self.cli_args.get("host"):
            self.cli_args.pop("host")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("disks")
        assert str(ex.value) == "Missing option. --host option is required for --ls-disks."

    def test_ls_disk_bad_host(self):
        self.cli_args["host"] = "BADHOST"
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("disks")
        assert str(ex.value) == "Host not found: BADHOST"

    def test_ls_disk_nodisk_host(self):
        self.cli_args["host"] = HOST2
        self.quads_cli_call("disks")
        assert self._caplog.messages[0] == f"No disks defined for {HOST2}"
