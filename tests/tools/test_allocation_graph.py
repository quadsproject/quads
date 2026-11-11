from datetime import datetime

from quads.tools.allocation_graph import (
    Allocation,
    build_allocations,
    render_allocations,
    window_for,
)

WINDOW_START = datetime(2026, 5, 1)
WINDOW_END = datetime(2026, 7, 31, 23, 59, 59)
HOSTS = [
    {"name": "h1", "model": "r640", "host_type": "scalelab"},
    {"name": "h2", "model": "r640", "host_type": "scalelab"},
    {"name": "h3", "model": "", "host_type": "scalelab"},
]


def test_window_for_covers_previous_current_and_next_month():
    start, end = window_for(datetime(2026, 6, 15, 12, 30))
    assert start == datetime(2026, 5, 1)
    assert end == datetime(2026, 7, 31, 23, 59, 59)


def test_build_allocations_merges_schedules_and_counts_models():
    schedules = {
        "h1": [
            {
                "assignment_id": 7,
                "start": "2026-06-02T00:00:00",
                "end": "2026-06-10T00:00:00",
                "cloud": "cloud02",
                "description": "ML <workload>",
                "owner": "alice",
                "ticket": "1234",
            }
        ],
        "h2": [
            {
                "assignment_id": 7,
                "start": "2026-06-02T00:00:00",
                "end": "2026-06-10T00:00:00",
                "cloud": "cloud02",
                "description": "ML <workload>",
                "owner": "alice",
                "ticket": "1234",
            }
        ],
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert len(allocations) == 1
    assert allocations[0].host_count == 2
    assert allocations[0].model_counts == {"r640": 2}


def test_build_allocations_parses_rfc1123_timestamps():
    schedules = {
        "h1": [
            {
                "assignment_id": 9,
                "start": "Mon, 01 Jun 2026 00:00:00 GMT",
                "end": "Tue, 30 Jun 2026 23:59:59 GMT",
                "cloud": "cloud02",
                "description": "RFC window",
                "owner": "bob",
                "ticket": "99",
            }
        ]
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert len(allocations) == 1
    assert allocations[0].start.date().isoformat() == "2026-06-01"


def test_build_allocations_clips_to_window_and_flags_it():
    schedules = {
        "h1": [
            {
                "assignment_id": 8,
                "start": "2026-04-20T00:00:00",
                "end": "2026-05-10T00:00:00",
                "cloud": "cloud02",
                "description": "Spans boundary",
                "owner": "carol",
                "ticket": "55",
            }
        ]
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert len(allocations) == 1
    assert allocations[0].clipped is True
    assert allocations[0].start == WINDOW_START


def test_build_allocations_skips_allocations_outside_window():
    schedules = {
        "h1": [
            {
                "assignment_id": 10,
                "start": "2026-01-01T00:00:00",
                "end": "2026-02-01T00:00:00",
                "cloud": "cloud02",
                "description": "Old",
                "owner": "dave",
                "ticket": "11",
            }
        ]
    }
    assert build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END) == []


def test_build_allocations_falls_back_for_missing_model():
    schedules = {
        "h3": [
            {
                "assignment_id": 11,
                "start": "2026-06-02T00:00:00",
                "end": "2026-06-03T00:00:00",
                "cloud": "cloud02",
                "description": "No model",
                "owner": "erin",
                "ticket": "12",
            }
        ]
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert allocations[0].model_counts == {"scalelab": 1}


def test_render_escapes_text_and_builds_ticket_link():
    allocation = Allocation(
        assignment_id=7,
        description="ML <workload>",
        owner="alice",
        ticket="1234",
        cloud="cloud02",
        start=datetime(2026, 6, 2),
        end=datetime(2026, 6, 10),
        host_count=4,
        model_counts={"r640": 4},
        clipped=False,
    )
    html = render_allocations(
        [allocation],
        WINDOW_START,
        WINDOW_END,
        datetime(2026, 6, 15, 12, 0),
        ticket_url="https://issues.example.com/browse",
        ticket_queue="SCALELAB",
    )
    assert "ML &lt;workload&gt;" in html
    assert 'href="https://issues.example.com/browse/SCALELAB-1234"' in html
    assert "r640 x 4" in html
    assert "height: 72px" in html
    assert "width: 96px" in html
    assert "May 2026" in html
    assert "July 2026" in html


def test_render_without_ticket_config_omits_link():
    allocation = Allocation(
        assignment_id=12,
        description="No ticket",
        owner="frank",
        ticket="",
        cloud="cloud02",
        start=datetime(2026, 6, 2),
        end=datetime(2026, 6, 10),
        host_count=1,
        model_counts={"r640": 1},
        clipped=False,
    )
    html = render_allocations([allocation], WINDOW_START, WINDOW_END, datetime(2026, 6, 15, 12, 0))
    assert "<a " not in html


def test_render_empty_allocations():
    html = render_allocations([], WINDOW_START, WINDOW_END, datetime(2026, 6, 15, 12, 0))
    assert "No allocations" in html
