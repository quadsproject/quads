"""Test fixtures for plugin tests"""

import pytest
from typing import Dict, Any

from quads.plugins.base import BasePlugin
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.interfaces.email import EmailPlugin
from quads.plugins.manager import PluginManager


class MockChatPlugin(ChatPlugin):
    """Mock chat plugin for testing"""

    name = "mock_chat"
    version = "1.0.0"
    description = "Mock chat plugin for testing"
    author = "Test"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._initialized = False

    def initialize(self, plugin_manager=None) -> bool:
        self._initialized = True
        return True

    async def send_message(self, message: str, channels=None, **kwargs) -> bool:
        return True


class MockEmailPlugin(EmailPlugin):
    """Mock email plugin for testing"""

    name = "mock_email"
    version = "1.0.0"
    description = "Mock email plugin for testing"
    author = "Test"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._initialized = False

    def initialize(self, plugin_manager=None) -> bool:
        self._initialized = True
        return True

    async def send_mail(self, subject: str, content: str, recipients, cc=None, **kwargs) -> bool:
        return True


class MockDayzeroPlugin(DayzeroPlugin):
    """Mock dayzero plugin for testing"""

    name = "mock_dayzero"
    version = "1.0.0"
    description = "Mock dayzero plugin for testing"
    author = "Test"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._initialized = False

    def initialize(self, plugin_manager=None) -> bool:
        self._initialized = True
        return True

    async def execute(self, host: str, cloud: str, schedule_data: dict) -> bool:
        return True


class MockDayzeroCloudPlugin(DayzeroPlugin):
    """Mock per-cloud dayzero plugin for testing"""

    name = "mock_dayzero_cloud"
    version = "1.0.0"
    description = "Mock per-cloud dayzero plugin for testing"
    author = "Test"
    run_mode = "per_cloud"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._initialized = False

    def initialize(self, plugin_manager=None) -> bool:
        self._initialized = True
        return True

    async def execute(self, host, cloud: str, schedule_data) -> bool:
        return True


class FailingDayzeroPlugin(DayzeroPlugin):
    """Dayzero plugin that raises during execute"""

    name = "failing_dayzero"
    version = "1.0.0"
    description = "Dayzero plugin that fails"
    author = "Test"

    def initialize(self, plugin_manager=None) -> bool:
        return True

    async def execute(self, host: str, cloud: str, schedule_data: dict) -> bool:
        raise RuntimeError("Simulated dayzero failure")


class FailingPlugin(BasePlugin):
    """Plugin that fails to initialize"""

    name = "failing"
    version = "1.0.0"
    description = "Plugin that fails"
    author = "Test"

    def initialize(self, plugin_manager=None) -> bool:
        return False


class ExceptionPlugin(BasePlugin):
    """Plugin that raises exception during init"""

    name = "exception"
    version = "1.0.0"
    description = "Plugin that raises exception"
    author = "Test"

    def initialize(self, plugin_manager=None) -> bool:
        raise RuntimeError("Simulated initialization error")


@pytest.fixture
def mock_config():
    """Mock plugin configuration"""
    return {
        "enabled": True,
        "webhook_url": "https://example.com/webhook",
        "default_channel": "#test",
    }


@pytest.fixture
def plugin_manager():
    """Create a fresh PluginManager instance for testing"""
    return PluginManager(config={})


@pytest.fixture
def mock_chat_plugin(mock_config):
    """Create a mock chat plugin instance"""
    return MockChatPlugin(mock_config)


@pytest.fixture
def mock_email_plugin(mock_config):
    """Create a mock email plugin instance"""
    return MockEmailPlugin(mock_config)


@pytest.fixture
def mock_dayzero_plugin(mock_config):
    """Create a mock dayzero plugin instance"""
    return MockDayzeroPlugin(mock_config)
