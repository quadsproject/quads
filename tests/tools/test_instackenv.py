#!/usr/bin/env python3
import os
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from quads.config import Config
from quads.tools.make_instackenv_json import cleanup_old_json_files, main, make_env_json
from tests.tools.test_base import TestBase


class TestInstackenv(TestBase):
    def test_make_instackenv_json(self):
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("openshift_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))
        main()
        with open(
            os.path.join(os.path.dirname(__file__), "../artifacts/cloud99_instackenv.json")
        ) as cloud99_instackenv:
            instackenv_list = list(cloud99_instackenv.readlines())
            instackenv_list = [line.strip() for line in instackenv_list]
        with open(
            os.path.join(os.path.dirname(__file__), "../artifacts/cloud99_ocpinventory.json")
        ) as cloud99_ocpinventory:
            ocpinventory_list = list(cloud99_ocpinventory.readlines())
            ocpinventory_list = [line.strip() for line in ocpinventory_list]
        with open(os.path.join(os.path.dirname(__file__), "fixtures/cloud99_env.json")) as cloud99_instackenv:
            fixtures_list = list(cloud99_instackenv.readlines())
            fixtures_list = [line.strip() for line in fixtures_list]
        assert instackenv_list == fixtures_list
        assert ocpinventory_list == fixtures_list


class TestCleanupOldJsonFiles(TestBase):
    """Test suite for the cleanup_old_json_files function."""

    def setup_method(self):
        """Set up test directory for each test."""
        self.test_dir = os.path.join(os.path.dirname(__file__), "../artifacts/cleanup_test/")
        os.makedirs(self.test_dir, exist_ok=True)
        Config.__setattr__("json_web_path", self.test_dir)

    def teardown_method(self):
        """Clean up test directory after each test."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def create_test_file(self, filename, age_seconds=0):
        """Helper to create a test file with a specific age."""
        filepath = os.path.join(self.test_dir, filename)
        with open(filepath, "w") as f:
            f.write("{}")

        # Set modification time to simulate age
        if age_seconds > 0:
            old_time = time.time() - age_seconds
            os.utime(filepath, (old_time, old_time))

        return filepath

    def test_cleanup_with_retention_zero(self, capsys):
        """Test cleanup deletes all old timestamped files when retention is 0."""
        Config.__setattr__("json_retention_days", 0)

        # Create old timestamped files (1 hour old)
        self.create_test_file("cloud01_instackenv.json_2026-04-13_10:30:45", age_seconds=3600)
        self.create_test_file("cloud02_ocpinventory.json_2026-04-13_09:15:30", age_seconds=7200)

        # Create current files (should not be deleted)
        self.create_test_file("cloud01_instackenv.json")

        cleanup_old_json_files()

        # Check that old timestamped files are deleted
        assert not os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json_2026-04-13_10:30:45"))
        assert not os.path.exists(os.path.join(self.test_dir, "cloud02_ocpinventory.json_2026-04-13_09:15:30"))

        # Check that current file still exists
        assert os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json"))

        # Verify log output
        captured = capsys.readouterr()
        assert "Cleaned up 2 old JSON file(s)" in captured.out

    def test_cleanup_with_retention_one_day(self, capsys):
        """Test cleanup respects 1-day retention policy."""
        Config.__setattr__("json_retention_days", 1)

        # Create files older than 1 day (2 days old)
        self.create_test_file("cloud01_instackenv.json_2026-04-11_10:30:45", age_seconds=2*86400)

        # Create files newer than 1 day (12 hours old)
        self.create_test_file("cloud02_instackenv.json_2026-04-13_01:30:45", age_seconds=12*3600)

        cleanup_old_json_files()

        # Old file should be deleted
        assert not os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json_2026-04-11_10:30:45"))

        # Recent file should remain
        assert os.path.exists(os.path.join(self.test_dir, "cloud02_instackenv.json_2026-04-13_01:30:45"))

        captured = capsys.readouterr()
        assert "Cleaned up 1 old JSON file(s)" in captured.out

    def test_cleanup_with_no_old_files(self, capsys):
        """Test cleanup when there are no old files to delete."""
        Config.__setattr__("json_retention_days", 1)

        # Create only recent files
        self.create_test_file("cloud01_instackenv.json_2026-04-13_14:30:45", age_seconds=60)

        cleanup_old_json_files()

        # File should still exist
        assert os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json_2026-04-13_14:30:45"))

        # No cleanup message should be printed
        captured = capsys.readouterr()
        assert "Cleaned up" not in captured.out

    def test_cleanup_skips_non_timestamped_files(self, capsys):
        """Test cleanup only targets timestamped files (containing ':')."""
        Config.__setattr__("json_retention_days", 0)

        # Create old timestamped file
        self.create_test_file("cloud01_instackenv.json_2026-04-13_10:30:45", age_seconds=3600)

        # Create non-timestamped files (should not be touched)
        self.create_test_file("cloud01_instackenv.json")
        self.create_test_file("cloud01_metadata.json")
        self.create_test_file("some_other_file.txt")

        cleanup_old_json_files()

        # Only timestamped file should be deleted
        assert not os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json_2026-04-13_10:30:45"))
        assert os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json"))
        assert os.path.exists(os.path.join(self.test_dir, "cloud01_metadata.json"))
        assert os.path.exists(os.path.join(self.test_dir, "some_other_file.txt"))

    def test_cleanup_handles_missing_directory(self, capsys):
        """Test cleanup gracefully handles non-existent directory."""
        Config.__setattr__("json_web_path", "/nonexistent/path/")

        # Should not raise an exception
        cleanup_old_json_files()

        # Should not print error since directory doesn't exist
        captured = capsys.readouterr()
        assert "ERROR" not in captured.out

    def test_cleanup_handles_permission_error(self, capsys):
        """Test cleanup handles files that cannot be deleted."""
        Config.__setattr__("json_retention_days", 0)

        # Create a file
        test_file = self.create_test_file("cloud01_instackenv.json_2026-04-13_10:30:45", age_seconds=3600)

        # Mock os.remove to raise PermissionError
        with patch("quads.tools.make_instackenv_json.os.remove") as mock_remove:
            mock_remove.side_effect = PermissionError("Permission denied")

            cleanup_old_json_files()

            # Check that error was logged
            captured = capsys.readouterr()
            assert "WARN: Cannot delete" in captured.out
            assert "Failed to delete 1 file(s)" in captured.out

    def test_cleanup_handles_concurrent_deletion(self, capsys):
        """Test cleanup handles race condition where file is deleted by another process."""
        Config.__setattr__("json_retention_days", 0)

        # Create a file
        self.create_test_file("cloud01_instackenv.json_2026-04-13_10:30:45", age_seconds=3600)

        # Mock os.remove to raise FileNotFoundError (simulating concurrent deletion)
        with patch("quads.tools.make_instackenv_json.os.remove") as mock_remove:
            mock_remove.side_effect = FileNotFoundError("File not found")

            # Should not raise an exception, should handle gracefully
            cleanup_old_json_files()

            # Should not print error for FileNotFoundError
            captured = capsys.readouterr()
            assert "Failed to delete" not in captured.out

    def test_cleanup_with_mixed_file_ages(self, capsys):
        """Test cleanup with a mix of old and new files."""
        Config.__setattr__("json_retention_days", 1)

        # Create files with various ages
        self.create_test_file("cloud01_instackenv.json_2026-04-10_10:30:45", age_seconds=3*86400)  # 3 days old
        self.create_test_file("cloud02_instackenv.json_2026-04-12_10:30:45", age_seconds=2*86400)  # 2 days old
        self.create_test_file("cloud03_instackenv.json_2026-04-13_10:30:45", age_seconds=12*3600)  # 12 hours old
        self.create_test_file("cloud04_ocpinventory.json_2026-04-13_14:00:00", age_seconds=3600)   # 1 hour old

        cleanup_old_json_files()

        # Files older than 1 day should be deleted
        assert not os.path.exists(os.path.join(self.test_dir, "cloud01_instackenv.json_2026-04-10_10:30:45"))
        assert not os.path.exists(os.path.join(self.test_dir, "cloud02_instackenv.json_2026-04-12_10:30:45"))

        # Files newer than 1 day should remain
        assert os.path.exists(os.path.join(self.test_dir, "cloud03_instackenv.json_2026-04-13_10:30:45"))
        assert os.path.exists(os.path.join(self.test_dir, "cloud04_ocpinventory.json_2026-04-13_14:00:00"))

        captured = capsys.readouterr()
        assert "Cleaned up 2 old JSON file(s)" in captured.out


class TestMakeEnvJsonPerformance(TestBase):
    """Test suite for performance optimizations in make_env_json."""

    @pytest.mark.asyncio
    async def test_make_env_json_batch_fetching(self, capsys):
        """Test that make_env_json fetches all hosts and assignments in batch."""
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))

        # Mock the QuadsApi to track API calls
        with patch("quads.tools.make_instackenv_json.quads") as mock_quads:
            # Set up mock return values
            mock_cloud = Mock()
            mock_cloud.name = "cloud99"
            mock_quads.get_clouds.return_value = [mock_cloud]

            mock_host = Mock()
            mock_host.name = "host1.example.com"
            mock_host.cloud.name = "cloud99"
            mock_host.interfaces = []
            mock_quads.get_hosts.return_value = [mock_host]

            mock_assignment = Mock()
            mock_assignment.ticket = "1234"
            mock_quads.get_active_assignments.return_value = [mock_assignment]

            await make_env_json("instackenv")

            # Verify batch calls were made
            mock_quads.get_clouds.assert_called_once()
            mock_quads.get_hosts.assert_called_once()
            mock_quads.get_active_assignments.assert_called_once()

            # Verify per-cloud calls were NOT made
            mock_quads.filter_hosts.assert_not_called()
            mock_quads.get_active_cloud_assignment.assert_not_called()

            # Verify performance logging
            captured = capsys.readouterr()
            assert "Fetching clouds and hosts" in captured.out
            assert "Processed" in captured.out

    @pytest.mark.asyncio
    async def test_make_env_json_skips_empty_clouds(self, capsys):
        """Test that make_env_json skips clouds with no hosts."""
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))

        with patch("quads.tools.make_instackenv_json.quads") as mock_quads:
            # Set up clouds
            mock_cloud1 = Mock()
            mock_cloud1.name = "cloud01"
            mock_cloud2 = Mock()
            mock_cloud2.name = "cloud02"
            mock_quads.get_clouds.return_value = [mock_cloud1, mock_cloud2]

            # Only cloud02 has hosts
            mock_host = Mock()
            mock_host.name = "host1.example.com"
            mock_host.cloud.name = "cloud02"
            mock_host.interfaces = []
            mock_quads.get_hosts.return_value = [mock_host]

            mock_quads.get_active_assignments.return_value = []

            await make_env_json("instackenv")

            # Check that empty cloud was skipped (no file created for cloud01)
            assert not os.path.exists(os.path.join(Config["json_web_path"], "cloud01_instackenv.json"))

    @pytest.mark.asyncio
    async def test_make_env_json_handles_assignment_fetch_error(self, capsys):
        """Test that make_env_json handles errors when fetching assignments."""
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))

        with patch("quads.tools.make_instackenv_json.quads") as mock_quads:
            mock_cloud = Mock()
            mock_cloud.name = "cloud99"
            mock_quads.get_clouds.return_value = [mock_cloud]

            mock_host = Mock()
            mock_host.name = "host1.example.com"
            mock_host.cloud.name = "cloud99"
            mock_host.interfaces = []
            mock_quads.get_hosts.return_value = [mock_host]

            # Simulate error fetching assignments
            mock_quads.get_active_assignments.side_effect = Exception("API Error")

            # Should not crash, should handle gracefully
            await make_env_json("instackenv")

            captured = capsys.readouterr()
            assert "WARN: Could not fetch assignments" in captured.out

    @pytest.mark.asyncio
    async def test_make_env_json_only_writes_when_data_exists(self):
        """Test that make_env_json only writes files when there's actual data."""
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("foreman_unavailable", True)
        test_dir = os.path.join(os.path.dirname(__file__), "../artifacts/empty_test/")
        os.makedirs(test_dir, exist_ok=True)
        Config.__setattr__("json_web_path", test_dir)

        try:
            with patch("quads.tools.make_instackenv_json.quads") as mock_quads:
                mock_cloud = Mock()
                mock_cloud.name = "emptycloud"
                mock_quads.get_clouds.return_value = [mock_cloud]

                # No hosts
                mock_quads.get_hosts.return_value = []
                mock_quads.get_active_assignments.return_value = []

                await make_env_json("instackenv")

                # No file should be created for empty cloud
                assert not os.path.exists(os.path.join(test_dir, "emptycloud_instackenv.json"))
        finally:
            import shutil
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_make_env_json_performance_logging(self, capsys):
        """Test that performance metrics are logged."""
        Config.__setattr__("openstack_management", True)
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("json_web_path", os.path.join(os.path.dirname(__file__), "../artifacts/"))

        with patch("quads.tools.make_instackenv_json.quads") as mock_quads:
            mock_cloud = Mock()
            mock_cloud.name = "cloud99"
            mock_quads.get_clouds.return_value = [mock_cloud]
            mock_quads.get_hosts.return_value = []
            mock_quads.get_active_assignments.return_value = []

            await make_env_json("instackenv")

            captured = capsys.readouterr()
            # Check for performance logging
            assert "INFO: Fetching clouds and hosts for instackenv" in captured.out
            assert "INFO: Processed" in captured.out
            assert "clouds" in captured.out
            assert "hosts" in captured.out
            assert "in" in captured.out  # timing info
            assert "s" in captured.out  # seconds
