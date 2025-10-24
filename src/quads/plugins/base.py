from abc import ABC, abstractmethod
from typing import Dict, Any
import logging


class BasePlugin(ABC):
    """Base class for all QUADS plugins"""

    # Plugin metadata
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"quads.plugins.{self.name}")
        self._enabled = config.get("enabled", True)

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize plugin resources"""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Cleanup plugin resources"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Verify plugin is operational"""
        pass

    @property
    def enabled(self) -> bool:
        return self._enabled
