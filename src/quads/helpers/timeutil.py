"""Timezone handling helpers.

QUADS stores and manipulates almost every datetime as a *naive* (timezone-less)
value expressed in the server's local time:

* database column defaults are set in the application with ``datetime.now()``
  (previously ``func.now()``, which stored the database session wall clock)
* most application writes use ``datetime.now()``
* CLI/API inputs such as schedule ``start``/``end`` are local wall-clock times

The scheme is only correct when the application server and the database both run
in UTC; ``flask --app quads.server.app check-timezones`` verifies this at deploy
time and exits non-zero when they differ.

Before these helpers existed the REST API simply stamped those naive local
values with a ``GMT`` label (``%a, %d %b %Y %H:%M:%S GMT``), which is only
accurate when the server happens to run in UTC.  On servers running in a
non-UTC timezone every timestamp returned by the API was off by the local UTC
offset (see https://github.com/quadsproject/quads/issues/709).

The helpers below centralize the two conversions needed to fix that:

* **Serialization (server side):** naive local datetimes are converted to real
  UTC before being written out with a ``GMT`` label, so the label is accurate
  for every consumer that parses the value as UTC.
* **Parsing (client side):** ``... GMT`` strings received from the API are read
  as UTC instants and, for in-repo consumers that keep comparing against
  ``datetime.now()``, re-anchored back to the local wall clock so their
  arithmetic is unchanged.
"""

from datetime import datetime, timezone

from werkzeug.http import http_date

#: Format used for datetimes on the QUADS REST API wire (RFC 1123, UTC).
HTTP_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


def local_timezone():
    """Return the local timezone, as a concrete ``datetime.timezone``.

    Matches the timezone that ``datetime.now()`` ("current local time") uses,
    which is the convention QUADS stores its naive datetimes in.
    """
    return datetime.now().astimezone().tzinfo


def ensure_utc(dt):
    """Return ``dt`` normalized to an aware UTC datetime.

    Naive datetimes are interpreted as server-local wall clock time, which is
    the convention the codebase uses everywhere (``datetime.now()``,
    ``func.now()`` defaults, user-supplied schedule times).  Aware datetimes
    are simply converted to UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_timezone())
    return dt.astimezone(timezone.utc)


def format_http_date(dt):
    """Serialize a datetime as an RFC 1123 string labeled ``GMT``.

    The value is normalized to real UTC first, so the ``GMT`` label reflects
    the actual instant.  This is what the REST API emits.  The output is
    locale-independent (English weekday and month names, as RFC 1123
    requires), matching the JSON provider which uses the same werkzeug
    formatter.
    """
    return http_date(ensure_utc(dt))


def format_iso_utc(dt):
    """Serialize a datetime as an ISO 8601 string with an explicit UTC offset."""
    return ensure_utc(dt).isoformat()


def parse_http_date(value):
    """Parse an RFC 1123 ``... GMT`` string as an aware UTC datetime.

    ``value`` may also already be a datetime, in which case it is returned
    unchanged.  Strings ending in ``UTC`` instead of ``GMT`` are accepted as
    well.
    """
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if text.endswith("UTC"):
        text = text[:-3] + "GMT"
    return datetime.strptime(text, HTTP_DATE_FORMAT).replace(tzinfo=timezone.utc)


def parse_http_date_local(value):
    """Parse an RFC 1123 ``... GMT`` string and return a naive local datetime.

    The GMT string is a UTC instant; it is converted into the local wall clock
    so that internal consumers comparing against ``datetime.now()`` keep
    working unchanged.
    """
    return parse_http_date(value).astimezone(local_timezone()).replace(tzinfo=None)


def parse_datetime(value):
    """Parse a datetime value coming from an API payload into a naive local datetime.

    Handles the formats the API and web frontend use in practice:

    * RFC 1123 ``... GMT`` strings (reported local time as UTC -> local wall clock)
    * ISO 8601 strings with or without a zone offset, with or without fractional seconds
    * plain ``%Y-%m-%d %H:%M`` / ``%Y-%m-%dT%H:%M`` strings (local wall clock)

    ``datetime`` instances are returned unchanged.  Anything that cannot be
    parsed raises ``ValueError``.
    """
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if text.endswith("GMT") or text.endswith("UTC"):
        return parse_http_date_local(text)

    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # Re-anchor any explicit offset back to local wall clock.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(local_timezone()).replace(tzinfo=None)
        return parsed

    raise ValueError(f"Invalid datetime format: {value!r}")
