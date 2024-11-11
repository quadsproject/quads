import logging

from quads.config import Config
from quads.tools.foreman_heal import rbac as foreman_heal_main
from tests.tools.test_base import TestBase


class TestForemanHeal(TestBase):
    def test_foreman_heal(self):
        Config.__setattr__("foreman_unavailable", True)
        self._caplog.set_level(logging.INFO)

        foreman_heal_main()

        assert len(self._caplog.messages) == 12
