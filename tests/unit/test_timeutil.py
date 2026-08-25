"""Unit tests for the timezone serialization helpers (issue #709).

The QUADS REST API stores and manipulates datetimes as naive values in the
server's *local* timezone, but must report them labeled ``GMT`` with the
*actual* UTC instant.  These tests exercise the conversion helpers under a
non-UTC local timezone so the offset correction is verified.

The local timezone is forced with ``TZ`` + ``time.tzset()`` per test and always
restored, so other test modules are unaffected.
"""

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import Flask, jsonify

from quads.helpers import timeutil
from quads.server.app import UtcJSONProvider


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
        with local_tz("America/New_York"):
            # 09:25 local (EDT, UTC-4) must become 13:25 UTC.
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.ensure_utc(local) == datetime(2026, 8, 17, 13, 25, 52, tzinfo=timezone.utc)

    def test_aware_dt_converted_to_utc(self):
        with local_tz("America/New_York"):
            aware = datetime(2026, 8, 17, 9, 25, 52, tzinfo=timezone.utc)
            assert timeutil.ensure_utc(aware) == datetime(2026, 8, 17, 9, 25, 52, tzinfo=timezone.utc)


class TestFormatHttpDate:
    def test_local_serialized_as_utc_gmt(self):
        with local_tz("America/New_York"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.format_http_date(local) == "Mon, 17 Aug 2026 13:25:52 GMT"

    def test_utc_tz_is_noop(self):
        with local_tz("UTC"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.format_http_date(local) == "Mon, 17 Aug 2026 09:25:52 GMT"


class TestParse:
    def test_roundtrip_through_gmt_string(self):
        with local_tz("America/New_York"):
            local = datetime(2026, 8, 17, 9, 25, 52)
            wire = timeutil.format_http_date(local)
            # The wire value is the real UTC instant.
            assert timeutil.parse_http_date(wire) == datetime(2026, 8, 17, 13, 25, 52, tzinfo=timezone.utc)
            # Re-anchoring gives back the original local wall clock.
            assert timeutil.parse_http_date_local(wire) == local
            assert timeutil.parse_datetime(wire) == local

    def test_parse_datetime_iso_with_offset(self):
        with local_tz("America/New_York"):
            assert timeutil.parse_datetime("2026-08-17T13:25:52+00:00") == datetime(2026, 8, 17, 9, 25, 52)

    def test_parse_datetime_naive_iso(self):
        with local_tz("America/New_York"):
            assert timeutil.parse_datetime("2026-08-17 09:25:52") == datetime(2026, 8, 17, 9, 25, 52)
            assert timeutil.parse_datetime("2026-08-17T09:25") == datetime(2026, 8, 17, 9, 25)


class TestJsonProvider:
    def test_jsonify_returns_utc_gmt(self):
        with local_tz("America/New_York"):
            app = Flask(__name__)
            app.json = UtcJSONProvider(app)

            @app.route("/t")
            def endpoint():
                return jsonify({"created_at": datetime(2026, 8, 17, 9, 25, 52)})

            payload = app.test_client().get("/t").get_json()
            assert payload == {"created_at": "Mon, 17 Aug 2026 13:25:52 GMT"}

    def test_jsonify_aware_utc_unchanged(self):
        with local_tz("America/New_York"):
            app = Flask(__name__)
            app.json = UtcJSONProvider(app)

            @app.route("/t")
            def endpoint():
                return jsonify({"last_used": datetime(2026, 8, 17, 13, 25, 52, tzinfo=timezone.utc)})

            payload = app.test_client().get("/t").get_json()
            assert payload == {"last_used": "Mon, 17 Aug 2026 13:25:52 GMT"}
