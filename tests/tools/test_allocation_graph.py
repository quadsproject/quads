import os
from datetime import datetime
from urllib.parse import parse_qs, urlparse

from quads.tools.allocation_graph import (
    Allocation,
    AllocationGraph,
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


def test_window_for_rolls_back_across_january():
    start, end = window_for(datetime(2026, 1, 15))
    assert start == datetime(2025, 12, 1)
    assert end == datetime(2026, 2, 28, 23, 59, 59)


def test_window_for_rolls_forward_across_december():
    start, end = window_for(datetime(2026, 12, 15))
    assert start == datetime(2026, 11, 1)
    assert end == datetime(2027, 1, 31, 23, 59, 59)


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


def test_build_allocations_merge_spans_min_start_and_max_end():
    schedules = {
        "h1": [
            {
                "assignment_id": 7,
                "start": "2026-06-05T00:00:00",
                "end": "2026-06-08T00:00:00",
                "cloud": "cloud02",
                "description": "early host",
                "owner": "alice",
                "ticket": "1234",
            }
        ],
        "h2": [
            {
                "assignment_id": 7,
                "start": "2026-06-02T00:00:00",
                "end": "2026-06-12T00:00:00",
                "cloud": "cloud02",
                "description": "late host",
                "owner": "alice",
                "ticket": "1234",
            }
        ],
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert len(allocations) == 1
    assert allocations[0].start == datetime(2026, 6, 2)
    assert allocations[0].end == datetime(2026, 6, 12)


def test_build_allocations_skips_schedules_without_assignment_id():
    schedules = {
        "h1": [
            {
                "assignment_id": None,
                "start": "2026-06-02T00:00:00",
                "end": "2026-06-10T00:00:00",
                "cloud": "cloud02",
                "description": "no assignment",
                "owner": "alice",
                "ticket": "1234",
            }
        ]
    }
    assert build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END) == []


def test_build_allocations_clips_end_to_window():
    schedules = {
        "h1": [
            {
                "assignment_id": 14,
                "start": "2026-07-20T00:00:00",
                "end": "2026-08-15T00:00:00",
                "cloud": "cloud02",
                "description": "Spans trailing boundary",
                "owner": "carol",
                "ticket": "56",
            }
        ]
    }
    allocations = build_allocations(schedules, HOSTS, WINDOW_START, WINDOW_END)
    assert len(allocations) == 1
    assert allocations[0].clipped is True
    assert allocations[0].end == WINDOW_END


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


def test_render_small_allocation_uses_minimum_content_height():
    allocation = Allocation(
        assignment_id=13,
        description="Small",
        owner="grace",
        ticket="",
        cloud="cloud02",
        start=datetime(2026, 6, 2),
        end=datetime(2026, 6, 10),
        host_count=1,
        model_counts={"r640": 1},
        clipped=False,
    )
    html = render_allocations([allocation], WINDOW_START, WINDOW_END, datetime(2026, 6, 15, 12, 0))
    assert "height: 44px" in html


def test_render_clamps_month_label_for_mid_month_window_start():
    html = render_allocations(
        [],
        datetime(2026, 6, 15),
        datetime(2026, 7, 31, 23, 59, 59),
        datetime(2026, 6, 15, 12, 0),
    )
    assert '<div class="ag-month-label" style="left: 0px;">June 2026</div>' in html


def test_render_sorts_allocations_by_start_time():
    # The earlier allocation carries the larger assignment_id so the ordering
    # can only be produced by the start-time key, not by assignment_id.
    late = Allocation(
        assignment_id=1,
        description="late",
        owner="heidi",
        ticket="",
        cloud="cloud02",
        start=datetime(2026, 6, 10),
        end=datetime(2026, 6, 11),
        host_count=1,
        model_counts={"r640": 1},
        clipped=False,
    )
    early = Allocation(
        assignment_id=2,
        description="early",
        owner="ivan",
        ticket="",
        cloud="cloud02",
        start=datetime(2026, 6, 2),
        end=datetime(2026, 6, 3),
        host_count=1,
        model_counts={"r640": 1},
        clipped=False,
    )
    html = render_allocations([late, early], WINDOW_START, WINDOW_END, datetime(2026, 6, 15, 12, 0))
    assert html.index("early") < html.index("late")


def test_generate_requests_seconds_and_writes_atomically(tmp_path):
    class FakeResponse:
        def json(self):
            return {
                "h1": [
                    {
                        "assignment_id": 1,
                        "start": "2026-06-02T00:00:00",
                        "end": "2026-06-03T00:00:00",
                        "cloud": "cloud02",
                        "description": "atomic",
                        "owner": "alice",
                        "ticket": "1",
                    }
                ]
            }

    class FakeQuads:
        def __init__(self):
            self.url = None

        def get(self, url):
            self.url = url
            return FakeResponse()

        def get_hosts(self):
            class Host:
                def as_dict(self):
                    return {"name": "h1", "model": "r640", "host_type": "scalelab"}

            return [Host()]

    class FakeConfig:
        def get(self, key, default=None):
            return {
                "visual_web_dir": str(tmp_path),
                "ticket_url": "",
                "ticket_queue": "",
            }.get(key, default)

    quads = FakeQuads()
    path = AllocationGraph(quads=quads, config=FakeConfig()).generate(now=datetime(2026, 6, 15, 12, 0))

    assert path == os.path.join(str(tmp_path), "graph", "allocation-graphic.html")
    query = parse_qs(urlparse(quads.url).query)
    assert query["start"] == ["2026-05-01T00:00:00"]
    assert query["end"] == ["2026-07-31T23:59:59"]
    # Written under graph/ so the top-level heatmap index glob never sweeps it.
    assert os.listdir(tmp_path) == ["graph"]
    assert os.listdir(os.path.join(tmp_path, "graph")) == ["allocation-graphic.html"]
    with open(path, encoding="utf-8") as handle:
        assert "atomic" in handle.read()
    assert oct(os.stat(path).st_mode & 0o777) == "0o644"
