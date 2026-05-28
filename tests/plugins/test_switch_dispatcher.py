"""Tests for SwitchDispatcher.verify returning the plugin's real result."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from quads.plugins.dispatchers.switch import SwitchDispatcher


def _dispatcher(plugin):
    plugin_manager = MagicMock()
    plugin_manager.get_plugins_by_type.return_value = []
    dispatcher = SwitchDispatcher(plugin_manager)
    dispatcher._plugins = [plugin]
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


def test_verify_one_plugin_fails_returns_false():
    good = MagicMock()
    good.verify = AsyncMock(return_value=True)
    bad = MagicMock()
    bad.verify = AsyncMock(return_value=False)
    dispatcher = _dispatcher(good)
    dispatcher._plugins = [good, bad]

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False


def test_verify_none_result_counts_as_success():
    plugin = MagicMock()
    plugin.verify = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is True


def test_verify_calls_all_plugins():
    good = MagicMock()
    good.verify = AsyncMock(return_value=True)
    other = MagicMock()
    other.verify = AsyncMock(return_value=True)
    dispatcher = _dispatcher(good)
    dispatcher._plugins = [good, other]

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is True
    good.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")
    other.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")


def test_configure_fail_closed():
    good = MagicMock()
    good.configure = AsyncMock(return_value=True)
    bad = MagicMock()
    bad.configure = AsyncMock(return_value=False)
    dispatcher = _dispatcher(good)
    dispatcher._plugins = [good, bad]

    assert asyncio.run(dispatcher.configure("host1.example.com", "cloud00", "cloud01")) is False


def test_modify_none_result_counts_as_success():
    plugin = MagicMock()
    plugin.modify = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.modify("host1.example.com", overrides={0: "1400"})) is True


def test_modify_exception_returns_false():
    plugin = MagicMock()
    plugin.modify = AsyncMock(side_effect=Exception("boom"))
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.modify("host1.example.com", overrides={0: "1400"})) is False


def test_ls_config_fail_closed():
    plugin = MagicMock()
    plugin.ls_config = AsyncMock(return_value=False)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.ls_config("cloud01")) is False


def test_ls_config_none_result_counts_as_success():
    plugin = MagicMock()
    plugin.ls_config = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.ls_config("cloud01")) is True
