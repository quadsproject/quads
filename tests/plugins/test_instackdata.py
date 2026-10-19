"""Tests for instackdata dayzero plugin"""

import asyncio

from unittest.mock import MagicMock, patch


def _schedules(*names):
    schedules = []
    for name in names:
        schedule = MagicMock()
        schedule.host.name = name
        schedules.append(schedule)
    return schedules


def _mock_api(mock_api_cls, schedules=None):
    mock_api = MagicMock()
    mock_api_cls.return_value = mock_api
    mock_api.get_active_cloud_assignment.return_value = MagicMock()
    mock_api.get_current_schedules.return_value = schedules or []
    return mock_api


def _run(plugin, cloud="cloud02"):
    plugin.initialize()
    plugin.logger = MagicMock()
    return asyncio.run(plugin.execute(cloud))


class TestInstackDataPluginMetadata:
    """Test InstackDataPlugin metadata"""

    def test_metadata(self):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        assert InstackDataPlugin.name == "instackdata"
        assert InstackDataPlugin.version == "1.0.0"
        assert InstackDataPlugin.run_mode == "per_cloud"

    def test_initialize(self):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        plugin = InstackDataPlugin({"enabled": True})
        assert plugin.initialize() is True


class TestInstackDataPluginExecute:
    """Test InstackDataPlugin execute logic"""

    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_no_active_assignment(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        mock_api = _mock_api(mock_api_cls)
        mock_api.get_active_cloud_assignment.return_value = None

        plugin = InstackDataPlugin({"enabled": True})
        assert _run(plugin) is True
        plugin.logger.info.assert_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_no_current_schedules(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls)

        plugin = InstackDataPlugin({"enabled": True})
        assert _run(plugin) is True

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_no_files_skips_ssh(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is True
        mock_ssh_cls.assert_not_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_timestamped_files_ignored(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json_2026-01-01_00:00:00").write_text("old")
        (tmp_path / "cloud02_ocpinventory.json_2026-01-01_00:00:00").write_text("old")

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is True
        mock_ssh_cls.assert_not_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_copies_existing_files(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com", "host02.example.com"))
        instackenv = '{"nodes": [{"name": "host01.example.com"}]}'
        ocpinventory = '{"nodes": [{"name": "host02.example.com"}]}'
        (tmp_path / "cloud02_instackenv.json").write_text(instackenv)
        (tmp_path / "cloud02_ocpinventory.json").write_text(ocpinventory)

        mock_ssh = MagicMock()
        mock_ssh.put_file.return_value = True
        mock_ssh_cls.return_value = mock_ssh

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is True

        mock_ssh_cls.assert_called_once_with("host01.example.com")
        assert mock_ssh.put_file.call_count == 2
        mock_ssh.disconnect.assert_called_once()
        assert mock_ssh.put_file.call_args_list[0][0] == (instackenv, "/root/cloud02_instackenv.json")
        assert mock_ssh.put_file.call_args_list[1][0] == (ocpinventory, "/root/cloud02_ocpinventory.json")

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_copies_only_existing_file(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')

        mock_ssh = MagicMock()
        mock_ssh.put_file.return_value = True
        mock_ssh_cls.return_value = mock_ssh

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is True

        mock_ssh.put_file.assert_called_once_with('{"nodes": []}', "/root/cloud02_instackenv.json")

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_uses_first_schedule_host(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host09.example.com", "host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')

        mock_ssh = MagicMock()
        mock_ssh.put_file.return_value = True
        mock_ssh_cls.return_value = mock_ssh

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is True

        mock_ssh_cls.assert_called_once_with("host09.example.com")

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_read_failure(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                assert _run(plugin) is False
        mock_ssh_cls.assert_not_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_unexpected_delivery_exception(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')
        mock_ssh_cls.side_effect = RuntimeError("boom")

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is False
        plugin.logger.error.assert_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_second_upload_failure_stops(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')
        (tmp_path / "cloud02_ocpinventory.json").write_text('{"nodes": []}')

        mock_ssh = MagicMock()
        mock_ssh.put_file.side_effect = [True, False]
        mock_ssh_cls.return_value = mock_ssh

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is False
        assert mock_ssh.put_file.call_count == 2
        mock_ssh.disconnect.assert_called_once()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_ssh_connection_failure(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin
        from quads.tools.external.ssh_helper import SSHHelperException

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')
        mock_ssh_cls.side_effect = SSHHelperException("Connection refused")

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is False
        plugin.logger.error.assert_called()

    @patch("quads.plugins.builtin.dayzero.instackdata.SSHHelper")
    @patch("quads.plugins.builtin.dayzero.instackdata.QuadsApi")
    def test_upload_failure(self, mock_api_cls, mock_ssh_cls, tmp_path):
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        _mock_api(mock_api_cls, _schedules("host01.example.com"))
        (tmp_path / "cloud02_instackenv.json").write_text('{"nodes": []}')

        mock_ssh = MagicMock()
        mock_ssh.put_file.return_value = False
        mock_ssh_cls.return_value = mock_ssh

        plugin = InstackDataPlugin({"enabled": True})
        with patch("quads.plugins.builtin.dayzero.instackdata.Config", {"json_web_path": str(tmp_path)}):
            assert _run(plugin) is False
        mock_ssh.disconnect.assert_called_once()
        plugin.logger.error.assert_called()


class TestInstackDataDiscovery:
    """Test that instackdata plugin is discoverable"""

    def test_instackdata_discovered(self):
        from quads.plugins.discovery import PluginDiscovery
        from quads.plugins.builtin.dayzero.instackdata import InstackDataPlugin

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("quads.plugins.builtin.dayzero")
        assert "instackdata" in plugins
        assert plugins["instackdata"] is InstackDataPlugin
