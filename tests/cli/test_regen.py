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
        Config.__setattr__("json_retention_days", 1)
        self.quads_cli_call("regen_instack")

        files = ["cloud99_ocpinventory.json", "cloud99_instackenv.json"]
        for f in files:
            assert os.path.exists(os.path.join(os.path.dirname(__file__), f"artifacts/{f}"))
        assert self._caplog.messages == [
            "Regenerated 'instackenv' for OpenStack Management.",
            "Regenerated 'ocpinventory' for OpenShift Management.",
        ]

    def test_regen_instack_with_cleanup(self, capsys):
        """Test that regen_instack performs cleanup of old files."""
        import time
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("openshift_management", False)
        test_dir = os.path.join(os.path.dirname(__file__), "artifacts/cleanup_regen/")
        os.makedirs(test_dir, exist_ok=True)
        Config.__setattr__("json_web_path", test_dir)
        Config.__setattr__("json_retention_days", 0)

        try:
            # Create an old timestamped file
            old_file = os.path.join(test_dir, "cloud99_instackenv.json_2026-04-12_10:30:45")
            with open(old_file, "w") as f:
                f.write("{}")
            # Make it old
            old_time = time.time() - 7200  # 2 hours ago
            os.utime(old_file, (old_time, old_time))

            # Run regen_instack
            self.quads_cli_call("regen_instack")

            # Verify old file was cleaned up
            assert not os.path.exists(old_file), "Old timestamped file should have been deleted"

            # Verify new files were created
            assert os.path.exists(os.path.join(test_dir, "cloud99_instackenv.json"))

        finally:
            import shutil
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)
