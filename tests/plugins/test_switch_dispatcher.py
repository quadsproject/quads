"""Tests for SwitchDispatcher.verify returning the plugin's real result."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from quads.plugins.dispatchers.switch import SwitchDispatcher


def _dispatcher(plugin):
    plugin_manager = MagicMock()
    plugin_manager.get_plugins_by_type.return_value = []
    dispatcher = SwitchDispatcher(plugin_manager)
    dispatcher._default_plugin = plugin
    return dispatcher


def test_verify_returns_plugin_result_false():
    plugin = MagicMock()
    plugin.verify = AsyncMock(return_value=False)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False
    plugin.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")


def test_verify_returns_plugin_result_true():
    plugin = MagicMock()
    plugin.verify = AsyncMock(return_value=True)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is True


def test_verify_exception_returns_false():
    plugin = MagicMock()
    plugin.verify = AsyncMock(side_effect=Exception("boom"))
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False


def test_verify_no_plugin_returns_false():
    plugin_manager = MagicMock()
    plugin_manager.get_plugins_by_type.return_value = []
    dispatcher = SwitchDispatcher(plugin_manager)
    dispatcher._default_plugin = None

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False
