import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from rich.table import Table

from quads.tools.lshw2meta import b2g, main


MINIMAL_LSHW_JSON = {
    "id": "host1.example.com",
    "class": "system",
    "children": [
        {
            "id": "cpu:0",
            "class": "processor",
            "handle": "DMI:0004",
            "vendor": "Intel Corporation",
            "product": "Intel(R) Xeon(R) Gold",
            "configuration": {"cores": "16", "threads": "32"},
        },
        {
            "id": "memory:0",
            "class": "memory",
            "handle": "DMI:0036",
            "size": 17179869184,
        },
        {
            "id": "network:0",
            "class": "network",
            "serial": "aa:bb:cc:dd:ee:ff",
            "vendor": "Intel Corporation",
            "logicalname": "eth0",
            "configuration": {"speed": "10Gbit/s"},
        },
        {
            "id": "disk:0",
            "class": "disk",
            "description": "NVM Express physical drive",
            "size": 1000204886016,
        },
    ],
}


RICH_LSHW_JSON = {
    "id": "host1.example.com",
    "class": "system",
    "children": [
        {
            "id": "cpu:0",
            "class": "processor",
            "handle": "DMI:0004",
            "vendor": "Intel Corporation",
            "product": "Intel(R) Xeon(R) Gold",
            "configuration": {"cores": "16", "threads": "32"},
        },
        {
            "id": "memory:0",
            "class": "memory",
            "handle": "DMI:0036",
            "size": 17179869184,
        },
        {
            "id": "network:0",
            "class": "network",
            "serial": "aa:bb:cc:dd:ee:ff",
            "vendor": "Intel Corporation",
            "logicalname": "eth0",
            "configuration": {"speed": "10Gbit/s"},
        },
        {
            "id": "disk:0",
            "class": "disk",
            "description": "NVM Express physical drive",
            "size": 1000204886016,
        },
        {
            "id": "display:0",
            "class": "display",
            "handle": "PCI:0000:01:00.0",
            "vendor": "NVIDIA Corporation",
            "product": "GeForce GT 710",
            "description": "VGA compatible controller",
            "configuration": {"driver": "nouveau"},
        },
    ],
}


class TestB2g:
    def test_b2g_binary(self):
        assert b2g(1024**3) == 1

    def test_b2g_metric(self):
        assert b2g(1000**3, metric=True) == 1


class TestLshw2metaMain:
    def _write_json(self, directory, filename, data):
        path = os.path.join(directory, filename)
        with open(path, "w") as f:
            json.dump(data, f)
        return path

    @patch("quads.tools.lshw2meta.quads")
    def test_main_empty_directory(self, mock_quads):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                main()
        mock_quads.get_host.assert_not_called()

    @patch("quads.tools.lshw2meta.quads")
    def test_main_processes_json_files(self, mock_quads):
        mock_host = MagicMock()
        mock_host.interfaces = []
        mock_host.memory = []
        mock_host.processors = []
        mock_quads.get_host.return_value = mock_host
        mock_quads.filter_hosts.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "host1.example.com.json", MINIMAL_LSHW_JSON)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                main()

        mock_quads.get_host.assert_called_once_with("host1.example.com")
        mock_quads.create_processor.assert_called_once()
        mock_quads.create_memory.assert_called_once()

    @patch("quads.tools.lshw2meta.quads")
    def test_main_skips_invalid_json(self, mock_quads):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_path = os.path.join(tmpdir, "bad.json")
            with open(bad_path, "w") as f:
                f.write("{invalid json}")
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                main()

        mock_quads.get_host.assert_not_called()

    @patch("quads.tools.lshw2meta.quads")
    def test_main_skips_unknown_host(self, mock_quads):
        mock_quads.get_host.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "unknown.json", MINIMAL_LSHW_JSON)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                main()

        mock_quads.create_processor.assert_not_called()

    @patch("quads.tools.lshw2meta.quads")
    def test_main_multiple_files_all_advance(self, mock_quads):
        mock_host = MagicMock()
        mock_host.interfaces = []
        mock_host.memory = []
        mock_host.processors = []
        mock_quads.get_host.return_value = mock_host
        mock_quads.filter_hosts.return_value = []

        host2_json = dict(MINIMAL_LSHW_JSON, id="host2.example.com")

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "host1.json", MINIMAL_LSHW_JSON)
            self._write_json(tmpdir, "host2.json", host2_json)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                with patch("quads.tools.lshw2meta.Progress") as mock_progress_cls:
                    mock_progress = MagicMock()
                    mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                    mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                    mock_progress.add_task.return_value = 0
                    main()

        mock_progress.add_task.assert_called_once_with("Importing metadata", total=2)
        assert mock_progress.advance.call_count == 2

    @patch("quads.tools.lshw2meta.quads")
    def test_main_prints_table_per_host(self, mock_quads):
        matching_iface = MagicMock()
        matching_iface.mac_address = "aa:bb:cc:dd:ee:ff"
        matching_iface.name = "eth0"
        mock_host = MagicMock()
        mock_host.interfaces = [matching_iface]
        mock_host.memory = []
        mock_host.processors = []
        mock_quads.get_host.return_value = mock_host
        mock_quads.filter_hosts.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "host1.json", RICH_LSHW_JSON)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                with patch("quads.tools.lshw2meta.Progress") as mock_progress_cls:
                    mock_progress = MagicMock()
                    mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                    mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                    mock_progress.add_task.return_value = 0
                    mock_progress.console.is_terminal = True
                    main()

        mock_progress.console.print.assert_called_once()
        printed_arg = mock_progress.console.print.call_args[0][0]
        assert isinstance(printed_arg, Table)
        # interface (matched MAC) + disk + memory + cpu + gpu = 5 rows
        assert printed_arg.row_count == 5
        assert [c.header for c in printed_arg.columns] == ["Component", "Detail", "Action"]
        # GPU branch was hit
        assert any(call.kwargs.get("processor_type") == "GPU"
                   or (call.args and len(call.args) >= 2 and isinstance(call.args[1], dict) and call.args[1].get("processor_type") == "GPU")
                   for call in mock_quads.create_processor.call_args_list)

    @patch("quads.tools.lshw2meta.quads")
    def test_main_plain_output_when_piped(self, mock_quads, capsys):
        mock_host = MagicMock()
        mock_host.interfaces = []
        mock_host.memory = []
        mock_host.processors = []
        mock_quads.get_host.return_value = mock_host
        mock_quads.filter_hosts.return_value = []

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "host1.json", MINIMAL_LSHW_JSON)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                with patch("quads.tools.lshw2meta.Progress") as mock_progress_cls:
                    mock_progress = MagicMock()
                    mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                    mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                    mock_progress.add_task.return_value = 0
                    mock_progress.console.is_terminal = False
                    main()

        # No Rich Table was printed
        for call in mock_progress.console.print.call_args_list:
            if call.args:
                assert not isinstance(call.args[0], Table)

        captured = capsys.readouterr()
        assert "host1.example.com:" in captured.out
        assert "cpu" in captured.out
        assert "memory" in captured.out
        assert "disk" in captured.out
        # No box-drawing characters in plain output
        assert "│" not in captured.out

    @patch("quads.tools.lshw2meta.quads")
    def test_main_table_includes_disk_update(self, mock_quads):
        existing_disk = MagicMock()
        existing_disk.disk_type = "nvme"
        existing_disk.size_gb = 1000
        existing_disk.count = 99
        existing_disk.id = "disk-id-1"

        existing_host = MagicMock()
        existing_host.disks = [existing_disk]

        mock_host = MagicMock()
        mock_host.name = "host1.example.com"
        mock_host.interfaces = []
        mock_host.memory = []
        mock_host.processors = []
        mock_quads.get_host.return_value = mock_host
        mock_quads.filter_hosts.return_value = [existing_host]

        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_json(tmpdir, "host1.json", MINIMAL_LSHW_JSON)
            with patch("quads.tools.lshw2meta.MD_DIR", tmpdir):
                with patch("quads.tools.lshw2meta.Progress") as mock_progress_cls:
                    mock_progress = MagicMock()
                    mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                    mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                    mock_progress.add_task.return_value = 0
                    mock_progress.console.is_terminal = True
                    main()

        mock_quads.update_disk.assert_called_once()
        mock_quads.create_disk.assert_not_called()
