import pytest

from quads.exceptions import CliException
from tests.cli.config import HOST1, HOST2
from tests.cli.test_base import TestBase


class TestMemory(TestBase):
    def test_ls_memory(self, capsys):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("memory")
        output = capsys.readouterr().out

        assert "Memory:" in output
        assert "DIMM1" in output
        assert "2048" in output
        assert "DIMM2" in output

    def test_ls_memory_missing_host(self):
        if self.cli_args.get("host"):
            self.cli_args.pop("host")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("memory")
        assert str(ex.value) == "Missing option. --host option is required for --ls-memory."

    def test_ls_memory_bad_host(self):
        self.cli_args["host"] = "BADHOST"
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("memory")
        assert str(ex.value) == "Host not found: BADHOST"

    def test_ls_memory_nomem_host(self):
        self.cli_args["host"] = HOST2
        self.quads_cli_call("memory")
        assert self._caplog.messages[0] == f"No memory defined for {HOST2}"
