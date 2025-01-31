import logging
import pytest

from quads.cli import QuadsCli

_logger = logging.getLogger("test_log")
_logger.setLevel(logging.INFO)
_logger.propagate = True


class TestBase:
    cli_args = {"datearg": None, "filter": None, "force": "False"}

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        self._caplog = caplog

    def quads_cli_call(self, action):
        qcli = QuadsCli(
            logger=_logger,
        )

        try:
            qcli.run(
                action=action,
                cli_args=self.cli_args,
            )
        except Exception as ex:
            raise ex
