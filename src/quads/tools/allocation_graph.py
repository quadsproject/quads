"""Aggregate QUADS schedules into allocation blocks and render an HTML fragment.

The aggregation and rendering helpers are intentionally free of HTTP and
filesystem access: callers pass plain API payloads and receive a self-contained
HTML fragment that can be embedded in the web UI.  This keeps the layout logic
testable without a running QUADS API server.  The ``AllocationGraph`` entrypoint
at the bottom of the module is the thin adapter that fetches the payloads and
writes the fragment to disk.
"""

import calendar
import html
import math
import os
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlencode

from quads.config import Config
from quads.helpers.timeutil import parse_datetime
from quads.quads_api import QuadsApi

DAY_WIDTH_PX = 12
MAX_BLOCK_HEIGHT_PX = 360
MAX_MACHINE_HEIGHT_PX = 18
MIN_MACHINE_HEIGHT_PX = 2
BLOCK_GAP_PX = 6

SECONDS_PER_DAY = 86400

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

CLOUD_PALETTE = (
    "#2563eb",
    "#16a34a",
    "#d97706",
    "#dc2626",
    "#7c3aed",
    "#0891b2",
    "#be185d",
    "#4d7c0f",
    "#9333ea",
    "#0f766e",
)


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
        left_px = offset_days * DAY_WIDTH_PX
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
    return f'<a href="{_escaped(href)}" target="_blank" rel="noopener">{_escaped(text)}</a>'


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


def _render_block(
    allocation: Allocation,
    top_px: int,
    color: str,
    window_start: datetime,
    ticket_url: str,
    ticket_queue: str,
) -> tuple[str, int]:
    duration_days = max(1, math.ceil((allocation.end - allocation.start).total_seconds() / SECONDS_PER_DAY))
    width_px = duration_days * DAY_WIDTH_PX
    height_px = max(
        MIN_MACHINE_HEIGHT_PX,
        min(MAX_BLOCK_HEIGHT_PX, allocation.host_count * MAX_MACHINE_HEIGHT_PX),
    )
    left_px = max(0, (allocation.start.date() - window_start.date()).days) * DAY_WIDTH_PX

    models = " · ".join(f"{_escaped(model)} x {count}" for model, count in sorted(allocation.model_counts.items()))
    meta = " · ".join(part for part in (_escaped(allocation.cloud), _escaped(allocation.owner)) if part)
    ticket_link = _ticket_link(ticket_url, ticket_queue, allocation.ticket)
    title = _escaped(_block_details(allocation))

    block = (
        f'<div class="ag-block" style="left: {left_px}px; top: {top_px}px; '
        f'width: {width_px}px; height: {height_px}px; background: {color};" title="{title}">'
        f'<div class="ag-block-title">{_escaped(allocation.description)}</div>'
        f'<div class="ag-block-meta">{meta}</div>'
        f'<div class="ag-block-ticket">{ticket_link}</div>'
        f'<div class="ag-block-models">{models}</div>'
        "</div>"
    )
    return block, height_px


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


_CSS = """
.allocation-graphic {
  font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  color: #1f2933;
  background: #f8fafc;
  border: 1px solid #cbd5e1;
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
  color: #334155;
}
.allocation-graphic .ag-generated {
  font-size: 12px;
  color: #64748b;
}
.allocation-graphic .ag-months {
  position: relative;
  height: 24px;
  margin-top: 16px;
  border-bottom: 1px solid #94a3b8;
}
.allocation-graphic .ag-month-label {
  position: absolute;
  top: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  white-space: nowrap;
}
.allocation-graphic .ag-timeline {
  position: relative;
  background-color: #ffffff;
  background-image: repeating-linear-gradient(
    to right,
    #e2e8f0 0,
    #e2e8f0 1px,
    transparent 1px,
    transparent 12px
  );
  border-bottom: 1px solid #94a3b8;
}
.allocation-graphic .ag-block {
  position: absolute;
  box-sizing: border-box;
  padding: 3px 5px;
  border: 1px solid rgba(15, 23, 42, 0.4);
  border-radius: 4px;
  color: #ffffff;
  overflow: hidden;
  font-size: 10px;
  line-height: 1.25;
}
.allocation-graphic .ag-block-title {
  font-weight: 600;
}
.allocation-graphic .ag-block-meta {
  opacity: 0.85;
}
.allocation-graphic .ag-block-ticket a {
  color: #ffffff;
  text-decoration: underline;
}
.allocation-graphic .ag-block-models {
  font-variant-numeric: tabular-nums;
}
.allocation-graphic .ag-empty {
  margin-top: 16px;
  padding: 24px;
  border: 1px dashed #94a3b8;
  border-radius: 6px;
  color: #475569;
  text-align: center;
}
.allocation-graphic .ag-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  font-size: 12px;
  color: #334155;
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
"""


def render_allocations(
    allocations: list[Allocation],
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
    ticket_url: str = "",
    ticket_queue: str = "",
) -> str:
    """Render allocations as a self-contained HTML fragment."""
    window_label = (
        f"{MONTH_NAMES[window_start.month - 1]} {window_start.year} - "
        f"{MONTH_NAMES[window_end.month - 1]} {window_end.year}"
    )
    window_days = max(1, math.ceil((window_end - window_start).total_seconds() / SECONDS_PER_DAY))
    timeline_width_px = window_days * DAY_WIDTH_PX

    clouds = sorted({allocation.cloud for allocation in allocations})
    cloud_colors = {cloud: CLOUD_PALETTE[index % len(CLOUD_PALETTE)] for index, cloud in enumerate(clouds)}

    parts = [
        '<div class="allocation-graphic">',
        f"<style>{_CSS}</style>",
        '<div class="ag-header">',
        '<div class="ag-title">Allocation Graphic</div>',
        f'<div class="ag-window">{_escaped(window_label)}</div>',
        f'<div class="ag-generated">Generated {_escaped(generated_at.strftime("%Y-%m-%d %H:%M"))}</div>',
        "</div>",
        f'<div class="ag-months" style="width: {timeline_width_px}px;">',
        *_month_labels(window_start, window_end),
        "</div>",
    ]

    if allocations:
        blocks = []
        top_px = 0
        for allocation in allocations:
            block, height_px = _render_block(
                allocation,
                top_px,
                cloud_colors[allocation.cloud],
                window_start,
                ticket_url,
                ticket_queue,
            )
            blocks.append(block)
            top_px += height_px + BLOCK_GAP_PX

        timeline_height_px = top_px + DAY_WIDTH_PX
        parts.append(
            f'<div class="ag-timeline" style="width: {timeline_width_px}px; '
            f'height: {timeline_height_px}px;">' + "".join(blocks) + "</div>"
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
                    "start": window_start.strftime("%Y-%m-%dT%H:%M"),
                    "end": window_end.strftime("%Y-%m-%dT%H:%M"),
                }
            )
        ).json()
        hosts = [host.as_dict() for host in self.quads.filter_hosts(data={"retired": False, "broken": False})]

        allocations = build_allocations(hosts_range, hosts, window_start, window_end)
        fragment = render_allocations(
            allocations,
            window_start,
            window_end,
            generated_at,
            ticket_url=self.config.get("ticket_url", ""),
            ticket_queue=self.config.get("ticket_queue", ""),
        )

        visual_web_dir = self.config.get("visual_web_dir")
        os.makedirs(visual_web_dir, exist_ok=True)
        path = os.path.join(visual_web_dir, "allocation-graphic.html")
        with open(path, "w", encoding="utf-8") as output:
            output.write(fragment)
        os.chmod(path, 0o644)
        return path
