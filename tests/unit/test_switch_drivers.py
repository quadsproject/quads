"""Tests for switch driver selection and validation."""

from collections import Counter
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from quads.plugins.switch_drivers import (
    SwitchDriverConfigError,
    enabled_switch_drivers,
    interface_vendor_counts_from_rows,
    parse_switch_driver_selection,
    update_switch_driver_config,
    validate_switch_driver_selection,
)


class TestParseSwitchDriverSelection:
    def test_accepts_vendor_list(self):
        assert parse_switch_driver_selection("arista,juniper") == {"arista", "juniper"}

    def test_accepts_generic_driver(self):
        assert parse_switch_driver_selection("network") == {"network"}

    def test_normalizes_case_and_whitespace(self):
        assert parse_switch_driver_selection(" Arista, JUNIPER ") == {"arista", "juniper"}

    def test_rejects_generic_with_vendor(self):
        with pytest.raises(SwitchDriverConfigError, match="cannot be combined"):
            parse_switch_driver_selection("network,arista")

    @pytest.mark.parametrize("value", ["", " ", "arista,", "arista,,juniper"])
    def test_rejects_empty_driver(self, value):
        with pytest.raises(SwitchDriverConfigError, match="one or more drivers"):
            parse_switch_driver_selection(value)

    def test_rejects_unknown_driver(self):
        with pytest.raises(SwitchDriverConfigError, match="Invalid switch driver.*cisco"):
            parse_switch_driver_selection("arista,cisco")


class TestValidateSwitchDriverSelection:
    def test_network_covers_all_vendors(self):
        validate_switch_driver_selection({"network"}, Counter({"juniper": 2, "arista": 3, "cisco": 1}))

    def test_both_vendor_drivers_cover_mixed_interfaces(self):
        validate_switch_driver_selection({"juniper", "arista"}, Counter({"juniper": 2, "arista": 3}))

    def test_missing_vendor_reports_interface_type(self):
        with pytest.raises(SwitchDriverConfigError) as exc:
            validate_switch_driver_selection({"juniper"}, Counter({"juniper": 2, "arista": 3}))

        message = str(exc.value)
        assert "There are 3 interface(s) defined with type 'arista'" in message
        assert "the 'arista' switch driver is disabled" in message
        assert "Enabled switch drivers: juniper." in message

    def test_unset_vendor_is_historical_juniper(self):
        counts = interface_vendor_counts_from_rows([(None, 1)])
        validate_switch_driver_selection({"juniper"}, counts)

    def test_requires_at_least_one_driver(self):
        with pytest.raises(SwitchDriverConfigError, match="At least one"):
            validate_switch_driver_selection(set(), Counter())

    def test_rejects_generic_with_vendor(self):
        with pytest.raises(SwitchDriverConfigError, match="cannot be combined"):
            validate_switch_driver_selection({"network", "juniper"}, Counter())

    def test_rejects_unknown_driver(self):
        with pytest.raises(SwitchDriverConfigError, match="Invalid switch driver"):
            validate_switch_driver_selection({"cisco"}, Counter())


class TestUpdateSwitchDriverConfig:
    def _write(self, tmp_path, plugins):
        path = tmp_path / "plugins.yml"
        path.write_text(yaml.safe_dump({"plugins": plugins}, sort_keys=False), encoding="utf-8")
        return path

    def test_enables_selected_and_disables_other_switch_drivers(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "juniper": {"enabled": True, "username": "scaleadmin"},
                "arista": {"enabled": False, "username": "admin"},
                "network": {"enabled": True},
                "email": {"enabled": True, "smtp_host": "mail.example.com"},
            },
        )

        plugins = update_switch_driver_config({"arista", "juniper"}, str(path))

        assert plugins["juniper"] == {"enabled": True, "username": "scaleadmin"}
        assert plugins["arista"]["enabled"] is True
        assert plugins["network"]["enabled"] is False
        assert plugins["email"] == {"enabled": True, "smtp_host": "mail.example.com"}
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["plugins"]["arista"]["enabled"] is True

    def test_generic_selection_disables_vendor_drivers(self, tmp_path):
        path = self._write(
            tmp_path,
            {
                "juniper": {"enabled": True},
                "arista": {"enabled": True},
                "network": {"enabled": False},
            },
        )

        plugins = update_switch_driver_config({"network"}, str(path))

        assert plugins["network"]["enabled"] is True
        assert plugins["juniper"]["enabled"] is False
        assert plugins["arista"]["enabled"] is False

    def test_adds_missing_selected_driver_entry(self, tmp_path):
        path = self._write(tmp_path, {"email": {"enabled": True}})

        plugins = update_switch_driver_config({"arista"}, str(path))

        assert plugins["arista"] == {"enabled": True}
        assert "juniper" not in plugins
        assert "network" not in plugins

    def test_rejects_invalid_selection(self, tmp_path):
        path = self._write(tmp_path, {"juniper": {"enabled": True}})

        with pytest.raises(SwitchDriverConfigError, match="cannot be combined"):
            update_switch_driver_config({"network", "juniper"}, str(path))


def test_enabled_switch_drivers_reads_plugin_config():
    config = {
        "juniper": {"enabled": True},
        "arista": {"enabled": False},
        "network": {"enabled": True},
    }
    assert enabled_switch_drivers(config) == {"juniper", "network"}


def test_startup_validation_rejects_missing_driver(monkeypatch):
    from quads.server import app as server_app

    query = MagicMock()
    query.group_by.return_value.all.return_value = [("juniper", 2), ("arista", 1)]
    monkeypatch.setattr(server_app, "db", MagicMock())
    server_app.db.session.query.return_value = query
    app = MagicMock()
    app.app_context.return_value = nullcontext()
    plugin_manager = SimpleNamespace(config={"plugins": {"juniper": {"enabled": True}}})

    with pytest.raises(RuntimeError, match="defined with type 'arista'.*driver is disabled"):
        server_app._validate_switch_driver_startup(app, plugin_manager)


def test_startup_validation_allows_generic_driver(monkeypatch):
    from quads.server import app as server_app

    query = MagicMock()
    query.group_by.return_value.all.return_value = [("juniper", 2), ("arista", 1)]
    monkeypatch.setattr(server_app, "db", MagicMock())
    server_app.db.session.query.return_value = query
    app = MagicMock()
    app.app_context.return_value = nullcontext()
    plugin_manager = SimpleNamespace(config={"plugins": {"network": {"enabled": True}}})

    server_app._validate_switch_driver_startup(app, plugin_manager)


def test_create_app_runs_startup_validation_when_enabled(monkeypatch):
    from quads.server import app as server_app
    from quads.server.config import TestingConfig

    class ValidatingConfig(TestingConfig):
        VALIDATE_SWITCH_DRIVERS = True

    validate = MagicMock()
    monkeypatch.setattr(server_app, "_validate_switch_driver_startup", validate)

    server_app.create_app(ValidatingConfig)

    validate.assert_called_once()
