"""Tests for SwitchDispatcher.verify returning the plugin's real result."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from quads.plugins.dispatchers.switch import SwitchDispatcher


def _dispatcher(plugin):
    plugin_manager = MagicMock()
    plugin_manager.get_plugins_by_type.return_value = []
    dispatcher = SwitchDispatcher(plugin_manager)
    dispatcher._plugins = [plugin]
    return dispatcher


def test_dispatcher_logs_all_enabled_switch_plugins(caplog):
    plugin_manager = MagicMock()
    juniper = MagicMock()
    juniper.name = "juniper"
    arista = MagicMock()
    arista.name = "arista"
    plugin_manager.get_plugins_by_type.return_value = [juniper, arista]

    with caplog.at_level(logging.INFO):
        SwitchDispatcher(plugin_manager)

    assert "Switch dispatcher loaded 2 plugins: ['juniper', 'arista']" in caplog.text


def test_dispatcher_logs_single_network_plugin(caplog):
    plugin_manager = MagicMock()
    network = MagicMock()
    network.name = "network"
    plugin_manager.get_plugins_by_type.return_value = [network]

    with caplog.at_level(logging.INFO):
        SwitchDispatcher(plugin_manager)

    assert "Switch dispatcher loaded 1 plugin: ['network']" in caplog.text


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
    bad = MagicMock()
    bad.verify = AsyncMock(side_effect=Exception("boom"))
    good = MagicMock()
    good.verify = AsyncMock(return_value=True)
    dispatcher = _dispatcher(bad)
    dispatcher._plugins = [bad, good]

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False
    bad.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")
    # an exception in one plugin must not skip the remaining plugins
    good.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")


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
    good.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")
    bad.verify.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")


def test_verify_none_result_fails_closed():
    plugin = MagicMock()
    plugin.verify = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.verify("host1.example.com", "cloud01", "cloud02")) is False


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
    good.configure.assert_awaited_once_with("host1.example.com", "cloud00", "cloud01")
    bad.configure.assert_awaited_once_with("host1.example.com", "cloud00", "cloud01")


def test_configure_stops_after_failure():
    bad = MagicMock()
    bad.configure = AsyncMock(return_value=False)
    good = MagicMock()
    good.configure = AsyncMock(return_value=True)
    dispatcher = _dispatcher(bad)
    dispatcher._plugins = [bad, good]

    assert asyncio.run(dispatcher.configure("host1.example.com", "cloud00", "cloud01")) is False
    bad.configure.assert_awaited_once()
    good.configure.assert_not_awaited()


def test_modify_none_result_fails_closed():
    plugin = MagicMock()
    plugin.modify = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.modify("host1.example.com", overrides={0: "1400"})) is False


def test_modify_exception_returns_false():
    plugin = MagicMock()
    plugin.modify = AsyncMock(side_effect=Exception("boom"))
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.modify("host1.example.com", overrides={0: "1400"})) is False


def test_modify_calls_all_plugins():
    first = MagicMock()
    first.modify = AsyncMock(return_value=True)
    second = MagicMock()
    second.modify = AsyncMock(return_value=True)
    dispatcher = _dispatcher(first)
    dispatcher._plugins = [first, second]

    assert asyncio.run(dispatcher.modify("host1.example.com", overrides={0: "1400"})) is True
    first.modify.assert_awaited_once_with("host1.example.com", False, {0: "1400"})
    second.modify.assert_awaited_once_with("host1.example.com", False, {0: "1400"})


def test_ls_config_fail_closed():
    good = MagicMock()
    good.ls_config = AsyncMock(return_value=True)
    bad = MagicMock()
    bad.ls_config = AsyncMock(return_value=False)
    dispatcher = _dispatcher(good)
    dispatcher._plugins = [good, bad]

    assert asyncio.run(dispatcher.ls_config("cloud01")) is False
    good.ls_config.assert_awaited_once_with("cloud01", False)
    bad.ls_config.assert_awaited_once_with("cloud01", False)


def test_ls_config_calls_all_plugins():
    first = MagicMock()
    first.ls_config = AsyncMock(return_value=True)
    second = MagicMock()
    second.ls_config = AsyncMock(return_value=True)
    dispatcher = _dispatcher(first)
    dispatcher._plugins = [first, second]

    assert asyncio.run(dispatcher.ls_config("cloud01")) is True
    first.ls_config.assert_awaited_once_with("cloud01", False)
    second.ls_config.assert_awaited_once_with("cloud01", False)


def test_ls_config_none_result_fails_closed():
    plugin = MagicMock()
    plugin.ls_config = AsyncMock(return_value=None)
    dispatcher = _dispatcher(plugin)

    assert asyncio.run(dispatcher.ls_config("cloud01")) is False
