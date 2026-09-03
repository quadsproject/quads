"""Unit tests for the timezone serialization helpers (issue #709).

The QUADS REST API stores and manipulates datetimes as naive values in the
server's *local* timezone, but must report them labeled ``GMT`` with the
*actual* UTC instant.  These tests exercise the conversion helpers under a
non-UTC local timezone so the offset correction is verified.

The tests run under ``Asia/Kolkata`` (UTC+05:30 fixed, no DST), so the expected
values are stable all year round and the non-whole-hour offset exercises the
``%f%z`` and re-anchor math harder than a whole-hour zone would.  The local
timezone is forced with ``TZ`` + ``time.tzset()`` per test and always restored,
so other test modules are unaffected.
"""

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from flask import Flask, jsonify

from quads.helpers import timeutil
from quads.server.app import UtcJSONProvider
from quads.server.database import check_db_timezone_consistency


@contextmanager
def local_tz(tzname):
    """Temporarily set the process local timezone to ``tzname``."""
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


class TestEnsureUtc:
    def test_naive_interpreted_as_local(self):
        with local_tz("Asia/Kolkata"):
            # 09:25 local (IST, UTC+5:30) must become 03:55 UTC.
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.ensure_utc(local) == datetime(2026, 8, 17, 3, 55, 52, tzinfo=timezone.utc)

    def test_aware_dt_converted_to_utc(self):
        with local_tz("Asia/Kolkata"):
            aware = datetime(2026, 8, 17, 9, 25, 52, tzinfo=timezone.utc)
            assert timeutil.ensure_utc(aware) == datetime(2026, 8, 17, 9, 25, 52, tzinfo=timezone.utc)


class TestFormatHttpDate:
    def test_local_serialized_as_utc_gmt(self):
        with local_tz("Asia/Kolkata"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.format_http_date(local) == "Mon, 17 Aug 2026 03:55:52 GMT"

    def test_utc_tz_is_noop(self):
        with local_tz("UTC"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.format_http_date(local) == "Mon, 17 Aug 2026 09:25:52 GMT"


class TestParse:
    def test_roundtrip_through_gmt_string(self):
        with local_tz("Asia/Kolkata"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            wire = timeutil.format_http_date(local)
            # The wire value is the real UTC instant.
            assert timeutil.parse_http_date(wire) == datetime(2026, 8, 17, 3, 55, 52, tzinfo=timezone.utc)
            # Re-anchoring gives back the original local wall clock.
            assert timeutil.parse_http_date_local(wire) == local
            assert timeutil.parse_datetime(wire) == local

    def test_parse_datetime_iso_with_offset(self):
        with local_tz("Asia/Kolkata"):
            assert timeutil.parse_datetime("2026-08-17T03:55:52+00:00") == datetime(2026, 8, 17, 9, 25, 52)

    def test_parse_datetime_naive_iso(self):
        with local_tz("Asia/Kolkata"):
            assert timeutil.parse_datetime("2026-08-17 09:25:52") == datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.parse_datetime("2026-08-17T09:25") == datetime(2026, 8, 17, 9, 25)

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("2026-08-17T09:25:52", datetime(2026, 8, 17, 9, 25, 52)),
            ("2026-08-17T09:25:52.284052", datetime(2026, 8, 17, 9, 25, 52, 284052)),
            ("2026-08-17 09:25:52.284052", datetime(2026, 8, 17, 9, 25, 52, 284052)),
            ("2026-08-17 09:25", datetime(2026, 8, 17, 9, 25)),
        ],
    )
    def test_parse_datetime_naive_formats(self, value, expected):
        with local_tz("Asia/Kolkata"):
            assert timeutil.parse_datetime(value) == expected

    def test_roundtrip_through_microsecond_iso(self):
        with local_tz("Asia/Kolkata"):
            local = datetime(2026, 8, 17, 9, 25, 52, 284052)
            assert timeutil.format_iso_utc(local) == "2026-08-17T03:55:52.284052+00:00"
            assert timeutil.parse_datetime(timeutil.format_iso_utc(local)) == local

    def test_parse_http_date_accepts_utc_suffix(self):
        with local_tz("Asia/Kolkata"):
            assert timeutil.parse_http_date("Mon, 17 Aug 2026 03:55:52 UTC") == datetime(
                2026, 8, 17, 3, 55, 52, tzinfo=timezone.utc
            )

    def test_parse_datetime_accepts_datetime_unchanged(self):
        with local_tz("Asia/Kolkata"):
            aware = datetime(2026, 8, 17, 3, 55, 52, tzinfo=timezone.utc)
            assert timeutil.parse_datetime(aware) is aware
            assert timeutil.parse_http_date(aware) is aware

    def test_parse_datetime_rejects_garbage(self):
        with local_tz("Asia/Kolkata"):
            with pytest.raises(ValueError):
                timeutil.parse_datetime("not a timestamp")


class TestJsonProvider:
    def test_jsonify_returns_utc_gmt(self):
        with local_tz("Asia/Kolkata"):
            app = Flask(__name__)
            app.json = UtcJSONProvider(app)

            @app.route("/t")
            def endpoint():
                return jsonify({"created_at": datetime(2026, 8, 17, 9, 25, 52)})

            payload = app.test_client().get("/t").get_json()
            assert payload == {"created_at": "Mon, 17 Aug 2026 03:55:52 GMT"}

    def test_jsonify_aware_utc_unchanged(self):
        with local_tz("Asia/Kolkata"):
            app = Flask(__name__)
            app.json = UtcJSONProvider(app)

            @app.route("/t")
            def endpoint():
                return jsonify({"last_used": datetime(2026, 8, 17, 13, 25, 52, tzinfo=timezone.utc)})

            payload = app.test_client().get("/t").get_json()
            assert payload == {"last_used": "Mon, 17 Aug 2026 13:25:52 GMT"}

    def test_create_app_installs_utc_json_provider(self):
        from quads.server.app import create_app

        with local_tz("Asia/Kolkata"):
            app = create_app("quads.server.config.TestingConfig")
            assert isinstance(app.json, UtcJSONProvider)

            @app.route("/t")
            def endpoint():
                return jsonify({"created_at": datetime(2026, 8, 17, 9, 25, 52)})

            # The request must run under the same forced timezone, since the
            # provider resolves the local offset at serialization time.
            payload = app.test_client().get("/t").get_json()
            assert payload == {"created_at": "Mon, 17 Aug 2026 03:55:52 GMT"}


class TestEnsureUtcJsonProviderGuard:
    def test_accepts_utc_provider(self):
        from quads.server.app import _ensure_utc_json_provider

        app = Flask(__name__)
        app.json = UtcJSONProvider(app)
        _ensure_utc_json_provider(app)

    def test_rejects_non_utc_provider(self):
        from flask.json.provider import DefaultJSONProvider
        from quads.server.app import _ensure_utc_json_provider

        app = Flask(__name__)
        app.json = DefaultJSONProvider(app)
        with pytest.raises(RuntimeError):
            _ensure_utc_json_provider(app)


class TestDbTimezoneConsistency:
    """The test database session runs in UTC, so results are deterministic."""

    def test_matching_timezones(self):
        with local_tz("UTC"):
            assert check_db_timezone_consistency() is True

    def test_mismatched_timezones(self):
        with local_tz("America/New_York"):
            assert check_db_timezone_consistency() is False

    def test_unreachable_db_returns_none(self, monkeypatch):
        from quads.server import database as database_module

        class _DeadEngine:
            def connect(self):
                raise RuntimeError("db down")

        # The check resolves ``engine or Engine`` against the database module
        # global, not the models import-time engine, so patch that global.
        monkeypatch.setattr(database_module, "Engine", _DeadEngine())
        with local_tz("UTC"):
            assert check_db_timezone_consistency() is None


class TestCheckTimezonesCommand:
    def _command_app(self):
        from quads.server.app import create_app

        return create_app("quads.server.config.TestingConfig")

    def test_exit_zero_when_matching(self):
        with local_tz("UTC"):
            result = self._command_app().test_cli_runner().invoke(args=["check-timezones"])
        assert result.exit_code == 0

    def test_exit_nonzero_when_mismatched(self, monkeypatch):
        from quads.server import app as app_module

        monkeypatch.setattr(app_module, "check_db_timezone_consistency", lambda engine: False)
        with local_tz("Asia/Kolkata"):
            result = self._command_app().test_cli_runner().invoke(args=["check-timezones"])
        assert result.exit_code == 1

    def test_exit_nonzero_when_db_unreachable(self, monkeypatch):
        from quads.server import app as app_module

        monkeypatch.setattr(app_module, "check_db_timezone_consistency", lambda engine: None)
        with local_tz("UTC"):
            result = self._command_app().test_cli_runner().invoke(args=["check-timezones"])
        assert result.exit_code == 1
