import os
from datetime import datetime

from quads.config import Config
from tests.cli.test_base import TestBase


class TestRegen(TestBase):
    def test_regen_heatmap(self):
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("visual_web_dir", os.path.join(os.path.dirname(__file__), "artifacts/"))
        self.quads_cli_call("regen_heatmap")

        files = [
            "index.html",
            "current.html",
            "next.html",
            f"{datetime.now().strftime('%Y-%m')}.html",
        ]
        for f in files:
            assert os.path.exists(os.path.join(os.path.dirname(__file__), f"artifacts/{f}"))
        assert self._caplog.messages == ["Regenerated web table heatmap."]

    def test_regen_instack(self):
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("openshift_management", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "artifacts/"))
        self.quads_cli_call("regen_instack")

        files = ["cloud99_ocpinventory.json", "cloud99_instackenv.json"]
        for f in files:
            assert os.path.exists(os.path.join(os.path.dirname(__file__), f"artifacts/{f}"))
        assert self._caplog.messages == [
            "Regenerated 'instackenv' for OpenStack Management.",
            "Regenerated 'ocpinventory' for OpenShift Management.",
        ]
