"""Aggregate QUADS schedules into allocation blocks and render an HTML fragment.

The aggregation and rendering helpers are intentionally free of HTTP and
filesystem access: callers pass plain API payloads and receive a self-contained
HTML fragment that can be embedded in the web UI.  This keeps the layout logic
testable without a running QUADS API server.  The ``AllocationGraph`` entrypoint
at the bottom of the module is the thin adapter that fetches the payloads and
writes the fragment to disk.
"""

import calendar
import hashlib
import html
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from quads.config import Config
from quads.helpers.timeutil import parse_datetime
from quads.quads_api import QuadsApi

DAY_WIDTH_PX = 12
# Fixed row geometry: every allocation is one lane of the same height so the
# page length scales linearly with the allocation count, not with machine
# count.  Machine count is shown as a label, never as block height (the old
# host_count*height encoding produced 360px-tall blocks and a page tens of
# thousands of pixels long once a month had many allocations).
ROW_HEIGHT_PX = 46
BAR_HEIGHT_PX = 22
BAR_TOP_PX = (ROW_HEIGHT_PX - BAR_HEIGHT_PX) // 2
LABEL_WIDTH_PX = 260

SECONDS_PER_DAY = 86400

# The graphic lives in its own subdirectory of visual_web_dir so the heatmap
# index generator (tools/simple_table_web.py), which globs the top level, never
# sweeps it into the "All Time" listing.  The /visual/graph route reads it here.
GRAPH_SUBDIR = "graph"
GRAPH_FILENAME = "allocation-graphic.html"

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def _cloud_color(cloud: str) -> str:
    """Deterministic bar color keyed by cloud name.

    A name-based hash keeps a cloud's color stable across regens (no drift when
    the active set changes) and avoids the collisions of a fixed small palette.
    Saturation and lightness are fixed and kept moderate so a wall of many
    clouds reads as a calm spread of hues rather than saturated noise.
    """
    # usedforsecurity=False: the hue is a color key, not a security digest, so
    # this keeps working on FIPS-enabled hosts where plain SHA1 raises.
    digest = hashlib.sha1((cloud or "unknown").encode("utf-8"), usedforsecurity=False).digest()
    hue = digest[0] / 255 * 360
    return f"hsl({hue:.0f}, 50%, 45%)"


@dataclass
class Allocation:
    assignment_id: int
    description: str
    owner: str
    ticket: str
    cloud: str
    start: datetime
    end: datetime
    host_count: int
    model_counts: dict[str, int]
    clipped: bool


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1)


def _month_end(year: int, month: int) -> datetime:
    _, last_day = calendar.monthrange(year, month)
    return datetime(year, month, last_day, 23, 59, 59)


def window_for(now: datetime) -> tuple[datetime, datetime]:
    """Return the previous, current, and next month window around ``now``."""
    previous_year, previous_month = now.year, now.month - 1
    if previous_month == 0:
        previous_year, previous_month = previous_year - 1, 12

    next_year, next_month = now.year, now.month + 1
    if next_month == 13:
        next_year, next_month = next_year + 1, 1

    return _month_start(previous_year, previous_month), _month_end(next_year, next_month)


def _schedule_times(schedule: dict, host_name: str) -> tuple[datetime, datetime]:
    try:
        return parse_datetime(schedule["start"]), parse_datetime(schedule["end"])
    except KeyError as exc:
        raise ValueError(f"Schedule for host {host_name!r} is missing {exc.args[0]!r}") from exc


def _model_for_host(host: dict | None) -> str:
    if host is None:
        return "unknown"
    model = (host.get("model") or "").strip()
    if model:
        return model
    host_type = (host.get("host_type") or "").strip()
    return host_type or "unknown"


def build_allocations(
    hosts_range: dict[str, list[dict]],
    hosts: list[dict],
    window_start: datetime,
    window_end: datetime,
) -> list[Allocation]:
    """Aggregate per-host schedules into allocations clipped to the window."""
    hosts_by_name = {}
    for host in hosts:
        name = host.get("name")
        if name:
            hosts_by_name[name] = host

    grouped: dict[int, dict] = {}
    for host_name, schedules in hosts_range.items():
        for schedule in schedules:
            start, end = _schedule_times(schedule, host_name)
            if end <= window_start or start >= window_end:
                continue

            assignment_id = schedule.get("assignment_id")
            if assignment_id is None:
                continue

            entry = grouped.get(assignment_id)
            if entry is None:
                entry = {
                    "description": schedule.get("description", ""),
                    "owner": schedule.get("owner", ""),
                    "ticket": schedule.get("ticket", ""),
                    "cloud": schedule.get("cloud", ""),
                    "start": start,
                    "end": end,
                    "clipped": False,
                    "hosts": {},
                }
                grouped[assignment_id] = entry
            else:
                entry["start"] = min(entry["start"], start)
                entry["end"] = max(entry["end"], end)

            if start < window_start or end > window_end:
                entry["clipped"] = True
            entry["hosts"][host_name] = _model_for_host(hosts_by_name.get(host_name))

    allocations = []
    for assignment_id, entry in grouped.items():
        model_counts: dict[str, int] = {}
        for model in entry["hosts"].values():
            model_counts[model] = model_counts.get(model, 0) + 1

        allocations.append(
            Allocation(
                assignment_id=assignment_id,
                description=str(entry["description"] or ""),
                owner=str(entry["owner"] or ""),
                ticket=str(entry["ticket"] or ""),
                cloud=str(entry["cloud"] or ""),
                start=max(entry["start"], window_start),
                end=min(entry["end"], window_end),
                host_count=len(entry["hosts"]),
                model_counts=model_counts,
                clipped=entry["clipped"],
            )
        )

    allocations.sort(key=lambda allocation: (allocation.start, allocation.assignment_id))
    return allocations


def _escaped(value: object) -> str:
    return html.escape(str(value))


def _month_labels(window_start: datetime, window_end: datetime) -> list[str]:
    labels = []
    year, month = window_start.year, window_start.month
    while True:
        month_start = _month_start(year, month)
        if month_start > window_end:
            break
        offset_days = (month_start.date() - window_start.date()).days
        left_px = max(0, offset_days * DAY_WIDTH_PX)
        label = f"{MONTH_NAMES[month - 1]} {year}"
        labels.append(f'<div class="ag-month-label" style="left: {left_px}px;">{_escaped(label)}</div>')
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return labels


def _ticket_link(ticket_url: str, ticket_queue: str, ticket: str) -> str:
    if not ticket_url or not ticket_queue or not ticket:
        return ""
    href = f"{ticket_url.rstrip('/')}/{ticket_queue}-{ticket}"
    text = f"{ticket_queue}-{ticket}"
    return f'<a href="{_escaped(href)}" target="_blank" rel="noopener noreferrer">{_escaped(text)}</a>'


def _block_details(allocation: Allocation) -> str:
    models = ", ".join(f"{model} x {count}" for model, count in sorted(allocation.model_counts.items()))
    details = [
        f"Assignment {allocation.assignment_id}",
        f"Description: {allocation.description}",
        f"Owner: {allocation.owner}",
        f"Cloud: {allocation.cloud}",
        f"Start: {allocation.start:%Y-%m-%d %H:%M}",
        f"End: {allocation.end:%Y-%m-%d %H:%M}",
        f"Hosts: {allocation.host_count}",
        f"Models: {models}",
    ]
    if allocation.ticket:
        details.append(f"Ticket: {allocation.ticket}")
    if allocation.clipped:
        details.append("Clipped to the visible window")
    return " | ".join(details)


def _render_row(
    allocation: Allocation,
    color: str,
    window_start: datetime,
    timeline_width_px: int,
    ticket_url: str,
    ticket_queue: str,
) -> str:
    """Render one allocation as a Gantt lane: sticky label gutter + timeline bar.

    The bar's geometry depends only on dates (``left``/``width``), never on the
    machine count, so one huge allocation can no longer dwarf the layout.  All
    the text lives in the always-visible gutter, so a short bar stays readable.
    """
    duration_days = max(1, math.ceil((allocation.end - allocation.start).total_seconds() / SECONDS_PER_DAY))
    width_px = duration_days * DAY_WIDTH_PX
    left_px = max(0, (allocation.start.date() - window_start.date()).days) * DAY_WIDTH_PX

    models = ", ".join(f"{_escaped(model)} x {count}" for model, count in sorted(allocation.model_counts.items()))
    hosts = f"{allocation.host_count} host" + ("" if allocation.host_count == 1 else "s")
    meta = " · ".join(part for part in (_escaped(allocation.cloud), _escaped(allocation.owner), hosts) if part)
    ticket_link = _ticket_link(ticket_url, ticket_queue, allocation.ticket)
    if ticket_link:
        meta = f"{meta} · {ticket_link}"
    title = _escaped(_block_details(allocation))
    clipped = " ag-bar--clipped" if allocation.clipped else ""

    return (
        '<div class="ag-row">'
        '<div class="ag-label">'
        f'<div class="ag-label-desc" title="{_escaped(allocation.description)}">{_escaped(allocation.description)}</div>'
        f'<div class="ag-label-meta">{meta}</div>'
        f'<div class="ag-label-models">{models}</div>'
        "</div>"
        f'<div class="ag-track" style="width: {timeline_width_px}px;">'
        f'<div class="ag-bar{clipped}" style="left: {left_px}px; width: {width_px}px; background: {color};" title="{title}"></div>'
        "</div>"
        "</div>"
    )


def _legend(cloud_colors: dict[str, str]) -> str:
    items = []
    for cloud, color in sorted(cloud_colors.items()):
        label = cloud or "unknown"
        items.append(
            f'<div class="ag-legend-item">'
            f'<span class="ag-legend-swatch" style="background: {color};"></span>'
            f"{_escaped(label)}</div>"
        )
    if not items:
        return ""
    return '<div class="ag-legend">' + "".join(items) + "</div>"


# Themeable chrome uses Bootstrap's data-bs-theme variables (with light-mode
# fallbacks) so the graphic adapts to dark pages like the rest of the site; the
# cloud bars keep their own colors.  The __FOO__ tokens are substituted from the
# layout constants so the CSS grid can never desync from the geometry Python
# computes for each bar.
_CSS = (
    """
.allocation-graphic {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: var(--bs-body-color, #1f2933);
  background: var(--bs-body-bg, #f8fafc);
  border: 1px solid var(--bs-border-color, #cbd5e1);
  border-radius: 8px;
  padding: 16px;
  overflow-x: auto;
}
.allocation-graphic .ag-header {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: baseline;
  justify-content: space-between;
}
.allocation-graphic .ag-title {
  font-size: 18px;
  font-weight: 600;
}
.allocation-graphic .ag-window {
  font-size: 14px;
  font-weight: 600;
  color: var(--bs-body-color, #334155);
}
.allocation-graphic .ag-generated {
  font-size: 12px;
  color: var(--bs-secondary-color, #64748b);
}
.allocation-graphic .ag-months-row,
.allocation-graphic .ag-row {
  display: flex;
  width: max-content;
  min-width: 100%;
}
.allocation-graphic .ag-months-row {
  margin-top: 16px;
}
.allocation-graphic .ag-corner,
.allocation-graphic .ag-label {
  width: __LABEL_WIDTH_PX__px;
  min-width: __LABEL_WIDTH_PX__px;
  position: sticky;
  left: 0;
  background: var(--bs-body-bg, #f8fafc);
}
.allocation-graphic .ag-corner {
  z-index: 2;
}
.allocation-graphic .ag-label {
  z-index: 1;
  box-sizing: border-box;
  padding: 2px 12px 2px 0;
  border-right: 1px solid var(--bs-border-color, #cbd5e1);
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.15;
  overflow: hidden;
}
.allocation-graphic .ag-label-desc {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.allocation-graphic .ag-label-meta {
  font-size: 11px;
  color: var(--bs-secondary-color, #64748b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.allocation-graphic .ag-label-meta a {
  color: inherit;
  text-decoration: underline;
}
.allocation-graphic .ag-label-models {
  font-size: 10px;
  color: var(--bs-secondary-color, #94a3b8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}
.allocation-graphic .ag-months {
  position: relative;
  flex: 0 0 auto;
  height: 24px;
  border-bottom: 1px solid var(--bs-border-color, #94a3b8);
}
.allocation-graphic .ag-month-label {
  position: absolute;
  top: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--bs-body-color, #334155);
  white-space: nowrap;
}
.allocation-graphic .ag-row {
  height: __ROW_HEIGHT_PX__px;
  border-bottom: 1px solid var(--bs-border-color, #e2e8f0);
}
.allocation-graphic .ag-track {
  position: relative;
  flex: 0 0 auto;
  background-image: repeating-linear-gradient(
    to right,
    var(--bs-border-color, #e2e8f0) 0,
    var(--bs-border-color, #e2e8f0) 1px,
    transparent 1px,
    transparent __DAY_WIDTH_PX__px
  );
}
.allocation-graphic .ag-bar {
  position: absolute;
  top: __BAR_TOP_PX__px;
  height: __BAR_HEIGHT_PX__px;
  box-sizing: border-box;
  border: 1px solid rgba(15, 23, 42, 0.25);
  border-radius: 4px;
}
.allocation-graphic .ag-bar--clipped {
  border-style: dashed;
}
.allocation-graphic .ag-empty {
  margin-top: 16px;
  padding: 24px;
  border: 1px dashed var(--bs-border-color, #94a3b8);
  border-radius: 6px;
  color: var(--bs-secondary-color, #475569);
  text-align: center;
}
.allocation-graphic .ag-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  font-size: 12px;
  color: var(--bs-body-color, #334155);
}
.allocation-graphic .ag-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.allocation-graphic .ag-legend-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 2px;
}
""".replace(
        "__DAY_WIDTH_PX__", str(DAY_WIDTH_PX)
    )
    .replace("__LABEL_WIDTH_PX__", str(LABEL_WIDTH_PX))
    .replace("__ROW_HEIGHT_PX__", str(ROW_HEIGHT_PX))
    .replace("__BAR_TOP_PX__", str(BAR_TOP_PX))
    .replace("__BAR_HEIGHT_PX__", str(BAR_HEIGHT_PX))
)


def render_allocations(
    allocations: list[Allocation],
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
    ticket_url: str = "",
    ticket_queue: str = "",
) -> str:
    """Render allocations as a self-contained HTML fragment."""
    allocations = sorted(allocations, key=lambda allocation: (allocation.start, allocation.assignment_id))
    window_label = (
        f"{MONTH_NAMES[window_start.month - 1]} {window_start.year} - "
        f"{MONTH_NAMES[window_end.month - 1]} {window_end.year}"
    )
    window_days = max(1, math.ceil((window_end - window_start).total_seconds() / SECONDS_PER_DAY))
    timeline_width_px = window_days * DAY_WIDTH_PX

    clouds = sorted({allocation.cloud for allocation in allocations})
    cloud_colors = {cloud: _cloud_color(cloud) for cloud in clouds}

    parts = [
        '<div class="allocation-graphic">',
        f"<style>{_CSS}</style>",
        '<div class="ag-header">',
        '<div class="ag-title">Allocation Graphic</div>',
        f'<div class="ag-window">{_escaped(window_label)}</div>',
        f'<div class="ag-generated">Generated {_escaped(generated_at.strftime("%Y-%m-%d %H:%M"))}</div>',
        "</div>",
        '<div class="ag-months-row">',
        '<div class="ag-corner"></div>',
        f'<div class="ag-months" style="width: {timeline_width_px}px;">',
        *_month_labels(window_start, window_end),
        "</div>",
        "</div>",
    ]

    if allocations:
        for allocation in allocations:
            parts.append(
                _render_row(
                    allocation,
                    cloud_colors[allocation.cloud],
                    window_start,
                    timeline_width_px,
                    ticket_url,
                    ticket_queue,
                )
            )
        parts.append(_legend(cloud_colors))
    else:
        parts.append('<div class="ag-empty">No allocations in this window.</div>')

    parts.append("</div>")
    return "\n".join(parts)


class AllocationGraph:
    """Fetch live QUADS schedules and write the allocation graphic fragment."""

    def __init__(self, quads: QuadsApi | None = None, config=None):
        self.config = config or Config
        self.quads = quads or QuadsApi(self.config)

    def generate(self, now: datetime | None = None) -> str:
        generated_at = now or datetime.now()
        window_start, window_end = window_for(generated_at)

        hosts_range = self.quads.get(
            "schedules/hosts_range?"
            + urlencode(
                {
                    "start": window_start.strftime("%Y-%m-%dT%H:%M:%S"),
                    "end": window_end.strftime("%Y-%m-%dT%H:%M:%S"),
                }
            )
        ).json()
        # All hosts, not just active ones: retiring a host does not delete its
        # schedules, so a recently retired/broken host with an allocation in the
        # window must still resolve to its real model instead of "unknown".
        hosts = [host.as_dict() for host in self.quads.get_hosts()]

        allocations = build_allocations(hosts_range, hosts, window_start, window_end)
        fragment = render_allocations(
            allocations,
            window_start,
            window_end,
            generated_at,
            ticket_url=self.config.get("ticket_url", ""),
            ticket_queue=self.config.get("ticket_queue", ""),
        )

        graph_dir = os.path.join(self.config.get("visual_web_dir"), GRAPH_SUBDIR)
        os.makedirs(graph_dir, exist_ok=True)
        path = os.path.join(graph_dir, GRAPH_FILENAME)
        fd, temp_path = tempfile.mkstemp(dir=graph_dir, prefix=".allocation-graphic-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(fragment)
            os.chmod(temp_path, 0o644)
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
        return path
