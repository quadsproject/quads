import logging
import sys

import pytest

_logger = logging.getLogger("test_log")
_logger.setLevel(logging.INFO)
_logger.propagate = True


class TestBase:
    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        caplog.set_level(logging.DEBUG)
        self._caplog = caplog

    @pytest.fixture(autouse=True)
    def capture_wrap(self):
        sys.stderr.close = lambda *args: None
        sys.stdout.close = lambda *args: None
        yield
