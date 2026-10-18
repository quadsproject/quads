"""Switch driver selection, validation and plugins.yml updates."""

import os
import stat
import tempfile
from collections import Counter
from collections.abc import Mapping
from typing import Iterable

import yaml

from quads.config import PLUGINS_CONF_PATH

SWITCH_DRIVER_NAMES = ("juniper", "arista", "network")
GENERIC_SWITCH_DRIVER = "network"
DEFAULT_VENDOR_DRIVER = "juniper"


class SwitchDriverConfigError(ValueError):
    """A switch driver selection cannot be applied safely."""


def parse_switch_driver_selection(value: str) -> set[str]:
    if value is None:
        raise SwitchDriverConfigError("A switch driver list is required")
    names = [name.strip().lower() for name in value.split(",")]
    if not names or any(not name for name in names):
        raise SwitchDriverConfigError(
            "Switch driver list must contain one or more drivers: " + ", ".join(SWITCH_DRIVER_NAMES)
        )
    unknown = sorted(set(names) - set(SWITCH_DRIVER_NAMES))
    if unknown:
        raise SwitchDriverConfigError(
            "Invalid switch driver(s): " + ", ".join(unknown) + ". Valid drivers: " + ", ".join(SWITCH_DRIVER_NAMES)
        )
    selected = set(names)
    if GENERIC_SWITCH_DRIVER in selected and len(selected) > 1:
        raise SwitchDriverConfigError(
            f"The generic '{GENERIC_SWITCH_DRIVER}' driver cannot be combined with vendor drivers; "
            f"enable either '{GENERIC_SWITCH_DRIVER}' alone or one or more of: "
            + ", ".join(name for name in SWITCH_DRIVER_NAMES if name != GENERIC_SWITCH_DRIVER)
        )
    return selected


def enabled_switch_drivers(plugin_config: Mapping | None) -> set[str]:
    enabled = set()
    for name in SWITCH_DRIVER_NAMES:
        entry = (plugin_config or {}).get(name)
        if entry is None:
            continue
        if not isinstance(entry, Mapping):
            raise SwitchDriverConfigError(f"plugins.{name} must be a mapping")
        if entry.get("enabled", False):
            enabled.add(name)
    return enabled


def interface_vendor_counts_from_rows(rows: Iterable) -> Counter:
    counts = Counter()
    for vendor, count in rows:
        counts[vendor or DEFAULT_VENDOR_DRIVER] += count
    return counts


def database_interface_vendor_counts() -> Counter:
    """Read interface vendor coverage directly from the database.

    The CLI must be able to repair a configuration that is preventing
    quads-server from starting, so this cannot depend on the API.
    """
    from sqlalchemy import create_engine, func
    from sqlalchemy.exc import SQLAlchemyError
    from sqlalchemy.orm import Session

    from quads.server.config import ProductionConfig
    from quads.server.models import Interface

    database_uri = os.environ.get("SQLALCHEMY_DATABASE_URI") or ProductionConfig.SQLALCHEMY_DATABASE_URI
    engine = None
    try:
        engine = create_engine(database_uri)
        with Session(engine) as session:
            rows = (
                session.query(Interface.switch_vendor, func.count(Interface.id))
                .group_by(Interface.switch_vendor)
                .all()
            )
    except SQLAlchemyError as exc:
        raise SwitchDriverConfigError(f"Could not read interfaces from the QUADS database: {exc}") from exc
    finally:
        if engine is not None:
            engine.dispose()
    return interface_vendor_counts_from_rows(rows)


def validate_switch_driver_selection(enabled: Iterable[str], interface_vendors: Mapping[str, int]) -> None:
    enabled = set(enabled)
    unknown = sorted(enabled - set(SWITCH_DRIVER_NAMES))
    if unknown:
        raise SwitchDriverConfigError("Invalid switch driver(s): " + ", ".join(unknown))
    if not enabled:
        raise SwitchDriverConfigError("At least one network switch driver must be enabled")
    if GENERIC_SWITCH_DRIVER in enabled and len(enabled) > 1:
        raise SwitchDriverConfigError(
            f"The generic '{GENERIC_SWITCH_DRIVER}' driver cannot be combined with vendor drivers"
        )
    if GENERIC_SWITCH_DRIVER in enabled:
        return

    missing = Counter()
    for vendor, count in interface_vendors.items():
        vendor = vendor or DEFAULT_VENDOR_DRIVER
        if vendor not in enabled and count:
            missing[vendor] += count
    if not missing:
        return

    lines = [
        f"There are {missing[vendor]} interface(s) defined with type '{vendor}', "
        f"but the '{vendor}' switch driver is disabled."
        for vendor in sorted(missing)
    ]
    lines.append("Enabled switch drivers: " + ", ".join(sorted(enabled)) + ".")
    raise SwitchDriverConfigError("\n".join(lines))


def update_switch_driver_config(selected: Iterable[str], path: str = None) -> dict:
    path = path or PLUGINS_CONF_PATH
    try:
        file_stat = os.stat(path)
        with open(path, "r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file) or {}
    except OSError as exc:
        raise SwitchDriverConfigError(f"Could not read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SwitchDriverConfigError(f"Could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SwitchDriverConfigError(f"Invalid plugins configuration in {path}: expected a mapping")

    plugins = data.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        raise SwitchDriverConfigError(f"Invalid plugins configuration in {path}: 'plugins' must be a mapping")

    selected = set(selected)
    validate_switch_driver_selection(selected, {})
    for name in SWITCH_DRIVER_NAMES:
        entry = plugins.get(name)
        if entry is None:
            if name in selected:
                plugins[name] = {"enabled": True}
            continue
        if not isinstance(entry, dict):
            raise SwitchDriverConfigError(f"Invalid plugins configuration in {path}: plugins.{name} must be a mapping")
        entry["enabled"] = name in selected

    directory = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".plugins.yml.", dir=directory, text=True)
    except OSError as exc:
        raise SwitchDriverConfigError(f"Could not write {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            yaml.safe_dump(data, tmp_file, sort_keys=False, default_flow_style=False)
        os.chmod(tmp_path, stat.S_IMODE(file_stat.st_mode))
        os.replace(tmp_path, path)
    except (OSError, yaml.YAMLError) as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise SwitchDriverConfigError(f"Could not write {path}: {exc}") from exc
    return plugins
