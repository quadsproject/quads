import importlib
import importlib.util
import logging

from pkgutil import iter_modules
from pathlib import Path
from typing import Dict, Type
from quads.plugins.base import BasePlugin


class PluginDiscovery:
    """Discovers and registers plugins"""

    def __init__(self):
        self.builtin_paths = [
            "quads.plugins.builtin.chat",
            "quads.plugins.builtin.cloud",
            "quads.plugins.builtin.email",
            "quads.plugins.builtin.hardware",
            "quads.plugins.builtin.provisioners",
            "quads.plugins.builtin.release",
            "quads.plugins.builtin.switches",
            "quads.plugins.builtin.ticketing",
            "quads.plugins.builtin.validators",
        ]
        self.external_path = Path("/opt/quads/plugins/")

    def discover_plugins(self) -> Dict[str, Type[BasePlugin]]:
        """Discover all available plugins"""
        plugins = {}

        # Discover built-in plugins
        for path in self.builtin_paths:
            plugins.update(self._discover_in_package(path))

        # Discover external plugins
        if self.external_path.exists():
            plugins.update(self._discover_in_directory(self.external_path))

        return plugins

    def _discover_in_package(self, package_name: str) -> Dict[str, Type[BasePlugin]]:
        """Load plugins from Python package"""
        plugins = {}
        try:
            package = importlib.import_module(package_name)
            for _, modname, _ in iter_modules(package.__path__):
                module = importlib.import_module(f"{package_name}.{modname}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BasePlugin)
                        and attr is not BasePlugin
                        and attr.name == modname
                    ):
                        plugins[modname] = attr
        except ImportError as e:
            logging.warning(f"Failed to load plugin package {package_name}: {e}")
        return plugins

    def _discover_in_directory(self, directory_path: Path) -> Dict[str, Type[BasePlugin]]:
        """Load plugins from directory"""
        plugins = {}
        for file in directory_path.glob("*.py"):
            if file.is_file() and file.stem != "__init__":
                try:
                    spec = importlib.util.spec_from_file_location(file.stem, file)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                                plugins[attr.name] = attr
                except Exception as e:
                    logging.warning(f"Failed to load plugin {file}: {e}")
        return plugins
