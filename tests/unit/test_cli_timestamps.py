"""Tests for CLI/API datetime handling under a non-UTC timezone (issue #709).

The REST API reports timestamps as real UTC instants labeled ``GMT`` (e.g.
``Mon, 17 Aug 2026 13:25:52 GMT`` for a local EDT time of 09:25).  The CLI must
re-anchor those back to the local wall clock so its internal lock/reservation
arithmetic (which compares against ``datetime.now()``) stays consistent.

These tests mock the HTTP API layer so no live server is needed.
"""

import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from quads.helpers.timeutil import format_http_date
from quads.server.models import Cloud

OS_TZ = "America/New_York"  # UTC-4 in summer (EDT)


@contextmanager
def force_tz(tzname):
    saved = os.environ.get("TZ")
    os.environ["TZ"] = tzname
    time.tzset()
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


def _make_cli():
    from quads.cli import QuadsCli
    from quads.config import Config
    from quads.quads_api import QuadsApi

    Config.load_from_yaml("conf/quads.yml")
    quads = QuadsApi(config=Config)
    logger = MagicMock()
    return QuadsCli(quads=quads, logger=logger), quads


class TestFreeCloudReservation:
    def test_reserved_math_uses_utc_reanchored_local_time(self):
        """The 'GMT' value from the API (real UTC) must be interpreted as UTC
        and mapped back to local time, keeping the 48h lock math correct."""
        with force_tz(OS_TZ):
            cli, quads = _make_cli()

            now_local = datetime.now()
            one_hour_ago_local = now_local - timedelta(hours=1)
            # What the fixed API returns for a redefinition 1h ago in EDT:
            wire_time = format_http_date(one_hour_ago_local)
            assert wire_time.endswith("GMT")

            free_cloud = MagicMock(spec=Cloud)
            free_cloud.name = "free01"
            free_cloud.last_redefined = wire_time  # raw GMT string (Cloud(*json))

            with patch.object(type(quads), "get_free_clouds", return_value=[free_cloud]):
                cli.run(action="free_cloud", cli_args={})

            messages = [c[0][0] for c in cli.logger.info.call_args_list if c[0]]
            reserved = [m for m in messages if "(reserved:" in m]
            assert reserved, f"expected a reserved message, got: {messages}"
            match = re.search(r"\(reserved: ([0-9.]+)hr ([0-9.]+)min", reserved[0])
            assert match, reserved[0]
            total_hours = float(match.group(1)) + float(match.group(2)) / 60
            # 48h lock - 1h elapsed => ~47h remaining.  A double shift (treating
            # the UTC value as local) would give ~51h and a sign error ~43h.
            assert 46.5 < total_hours < 47.6, total_hours

    def test_free_cloud_no_reservation_for_old_redefinition(self):
        with force_tz(OS_TZ):
            cli, quads = _make_cli()

            free_cloud = MagicMock(spec=Cloud)
            free_cloud.name = "free01"
            free_cloud.last_redefined = format_http_date(datetime.now() - timedelta(days=10))

            with patch.object(type(quads), "get_free_clouds", return_value=[free_cloud]):
                cli.run(action="free_cloud", cli_args={})

            messages = [c[0][0] for c in cli.logger.info.call_args_list if c[0]]
            assert messages == ["free01"], messages
