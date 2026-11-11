# Lab Allocation Graphic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate an HTML/CSS allocation graphic covering the previous, current, and next month, with blocks sized by machine count and duration and containing description, ticket link, and model counts.

**Architecture:** A new `quads.tools.allocation_graph` module fetches schedules and host metadata through the existing `QuadsApi`, aggregates allocations by assignment, and renders a pure HTML fragment. The fragment is written to `visual_web_dir`, exposed at `/visual/graph`, refreshed by a new `--regen-graph` CLI action, and documented alongside the existing heatmap.

**Tech Stack:** Python 3.11+, `QuadsApi`, Flask, Jinja2, HTML/CSS, pytest, flake8, black.

**Spec:** `docs/superpowers/specs/2026-11-11-allocation-graphic-design.md`

## Global Constraints

- No new runtime dependencies.
- Read `visual_web_dir`, `ticket_url`, and `ticket_queue` from `Config` at call time, not import time.
- The generated artifact is an HTML fragment, not a full document; it must not contain `<html>` or `<body>`.
- Escape every user-controlled string with `html.escape`.
- Use the existing `parse_datetime` helper for API timestamps.
- Black line length 119; flake8 config is in `.flake8`.
- Core renderer tests must not require a live API server.

## Review Focus

- API timestamps may arrive as RFC 1123 `GMT` strings or ISO strings; both must parse or raise a clear error, not crash the page.
- Allocations may start before or end after the three-month window; blocks must be clipped and marked in the tooltip.
- Hosts may have an empty or missing `model`; fall back to `host_type`, then `unknown`, without a `KeyError`.
- Tickets may be absent or contain HTML-special characters; links and text must be escaped and omitted cleanly.
- Empty schedule data must produce a valid page with a clear "No allocations" message, not a division-by-zero or broken layout.

---

### Task 1: Allocation aggregation and rendering core

**Files:**
- Create: `src/quads/tools/allocation_graph.py`
- Test: `tests/tools/test_allocation_graph.py`

**Interfaces:**
- Consumes: `quads.helpers.timeutil.parse_datetime`; `html.escape`.
- Produces:
  - `window_for(now: datetime) -> tuple[datetime, datetime]` returning first day of previous month at 00:00 and last day of next month at 23:59:59.
  - `Allocation` dataclass with fields `assignment_id: int`, `description: str`, `owner: str`, `ticket: str`, `cloud: str`, `start: datetime`, `end: datetime`, `host_count: int`, `model_counts: dict[str, int]`, `clipped: bool`.
  - `build_allocations(hosts_range: dict[str, list[dict]], hosts: list[dict], window_start: datetime, window_end: datetime) -> list[Allocation]`.
  - `render_allocations(allocations: list[Allocation], window_start: datetime, window_end: datetime, generated_at: datetime, ticket_url: str = "", ticket_queue: str = "") -> str`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/tools/test_allocation_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'quads.tools.allocation_graph'`.

- [ ] **Step 3: Implement the module**

Create `src/quads/tools/allocation_graph.py` with the interfaces above. Use `calendar.monthrange` for month boundaries, `parse_datetime` for schedule values, and `html.escape` for every rendered string. Compute layout constants in the module: `DAY_WIDTH_PX = 12`, `MAX_BLOCK_HEIGHT_PX = 360`, `MAX_MACHINE_HEIGHT_PX = 18`, `MIN_MACHINE_HEIGHT_PX = 2`, `BLOCK_GAP_PX = 6`. For a single allocation with four machines, this yields `height: 72px`; eight days yields `width: 96px`. Render blocks with inline `left`, `top`, `width`, `height`, and `background` styles, and include the full details in a `title` attribute. Render a `<style>` block scoped under `.allocation-graphic`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/tools/test_allocation_graph.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add src/quads/tools/allocation_graph.py tests/tools/test_allocation_graph.py
git commit -m "feat: add allocation graphic aggregation and renderer"
```

---

### Task 2: Generation entrypoint and CLI action

**Files:**
- Modify: `src/quads/tools/allocation_graph.py` (add `AllocationGraph` and `generate`)
- Modify: `src/quads/cli/parser.py` (add `--regen-graph`)
- Modify: `src/quads/cli/cli.py` (import and add `action_regen_graph`)
- Test: `tests/cli/test_regen.py` (add `test_regen_graph`)

**Interfaces:**
- Consumes: `build_allocations`, `render_allocations`, and `window_for` from Task 1; `QuadsApi`; `Config`.
- Produces:
  - `AllocationGraph(quads: QuadsApi | None = None, config=None)` with `generate(now: datetime | None = None) -> str` writing `{visual_web_dir}/allocation-graphic.html` and returning its path.
  - CLI action `regen_graph` logging exactly `Regenerated allocation graphic.`

- [ ] **Step 1: Write the failing CLI test**

```python
def test_regen_graph(self):
    Config.__setattr__("foreman_unavailable", True)
    Config.__setattr__("visual_web_dir", os.path.join(os.path.dirname(__file__), "artifacts/"))
    self.quads_cli_call("regen_graph")

    path = os.path.join(os.path.dirname(__file__), "artifacts/allocation-graphic.html")
    assert os.path.exists(path)
    assert self._caplog.messages == ["Regenerated allocation graphic."]
    os.remove(path)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/cli/test_regen.py::TestRegen::test_regen_graph -v`
Expected: FAIL because `regen_graph` is not a recognized action.

- [ ] **Step 3: Implement the entrypoint and CLI action**

Add `AllocationGraph` to `src/quads/tools/allocation_graph.py`. It should fetch `schedules/hosts_range` and `hosts?retired=False&broken=False` through the supplied `QuadsApi` (or `QuadsApi(Config)`), convert hosts with `as_dict()`, build allocations, render the fragment, create `visual_web_dir` if needed, write `allocation-graphic.html` with mode `0o644`, and return the path. Read `ticket_url` and `ticket_queue` from `Config` inside `generate`. Add the `--regen-graph` argument to the parser action group with `const="regen_graph"`, and add `action_regen_graph` to `QuadsCli` calling `AllocationGraph().generate()` and logging `Regenerated allocation graphic.`

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/cli/test_regen.py::TestRegen::test_regen_graph -v`
Expected: PASS (requires the tox API server; if running locally without it, run the unit tests from Task 1 instead and note the CLI test is covered in CI).

- [ ] **Step 5: Commit**

```bash
git add src/quads/tools/allocation_graph.py src/quads/cli/parser.py src/quads/cli/cli.py tests/cli/test_regen.py
git commit -m "feat: add --regen-graph CLI action"
```

---

### Task 3: Web route, template, and navigation

**Files:**
- Modify: `src/quads/web/blueprints/visual.py` (add `/graph` route)
- Modify: `src/quads/web/app.py` (add navbar item)
- Create: `src/quads/web/templates/wiki/allocation_graph.html`
- Test: `tests/web/test_allocation_graph.py`

**Interfaces:**
- Consumes: `VISUAL_DIR` and the generated `allocation-graphic.html` from Task 2.
- Produces: `GET /visual/graph` returning the fragment inside `wiki/allocation_graph.html`, or a 404 with a clear message when the file is missing.

- [ ] **Step 1: Write the failing web tests**

```python
import os

import pytest

import quads.web.blueprints.visual as visual_module
from quads.web.app import create_app


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    original = visual_module.VISUAL_DIR
    visual_module.VISUAL_DIR = str(tmp_path_factory.mktemp("visual"))
    try:
        yield create_app()
    finally:
        visual_module.VISUAL_DIR = original


def test_graph_served(app):
    path = os.path.join(visual_module.VISUAL_DIR, "allocation-graphic.html")
    with open(path, "w") as handle:
        handle.write("<div id='graph'>ok</div>")
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 200
    assert "<div id='graph'>ok</div>" in response.get_data(as_text=True)


def test_graph_missing_returns_404(app):
    path = os.path.join(visual_module.VISUAL_DIR, "allocation-graphic.html")
    if os.path.exists(path):
        os.remove(path)
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 404
    assert "Allocation graphic has not been generated" in response.get_data(as_text=True)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/web/test_allocation_graph.py -v`
Expected: FAIL with 404 for `/visual/graph` (route not found) and a missing template.

- [ ] **Step 3: Implement the route, template, and navbar item**

In `visual.py`, add a `graph` route that reads `allocation-graphic.html` from `VISUAL_DIR`, passes its contents as `html_content`, and renders `wiki/allocation_graph.html`; use `abort(404, description="Allocation graphic has not been generated")` when the file is absent. Create the template extending `base.html`, with a `Monthly Usage`-style heading and `{{ html_content|safe }}`. In `app.py`, add `View(text="Allocation Graphic", endpoint="visual.graph")` to the existing Visuals subgroup.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/web/test_allocation_graph.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/quads/web/blueprints/visual.py src/quads/web/app.py src/quads/web/templates/wiki/allocation_graph.html tests/web/test_allocation_graph.py
git commit -m "feat: serve allocation graphic in the web UI"
```

---

### Task 4: Cron and documentation

**Files:**
- Modify: `cron/quads`
- Modify: `README.md` (cron command table)
- Modify: `docs/quads-workflow.md` (visualization section)

**Interfaces:**
- Consumes: the `--regen-graph` action from Task 2 and the `/visual/graph` route from Task 3.
- Produces: documented regeneration and access instructions.

- [ ] **Step 1: Add the commented cron entry**

Add `# * quads --regen-graph (keeps the allocation graphic up to date)` to the header comments and a commented `*/20` cron line using `flock -n /tmp/allocationgraphic.lock -c "quads --regen-graph"`, matching the existing heatmap entry style.

- [ ] **Step 2: Update the README command table**

Add `| quads --regen-graph | visualization | keeps the lab allocation graphic up to date |` next to the `--regen-heatmap` row.

- [ ] **Step 3: Update the workflow docs**

Add an "Example: Allocation Graphic" section near "Example: Systems Visualization Map" describing the three-month window, block sizing, ticket links, and the `/visual/graph` page.

- [ ] **Step 4: Verify the documentation references**

Run: `grep -rn "regen-graph\|visual/graph\|Allocation Graphic" cron README.md docs/quads-workflow.md`
Expected: each new reference is present.

- [ ] **Step 5: Commit**

```bash
git add cron/quads README.md docs/quads-workflow.md
git commit -m "docs: document the allocation graphic"
```

---

### Task 5: Final verification and spec commit

**Files:**
- Verify: all files from Tasks 1-4
- Add: `docs/superpowers/specs/2026-11-11-allocation-graphic-design.md`
- Add: `docs/superpowers/plans/2026-11-11-allocation-graphic.md`

- [ ] **Step 1: Run the focused test suite**

Run: `pytest tests/tools/test_allocation_graph.py tests/web/test_allocation_graph.py -v`
Expected: PASS.

- [ ] **Step 2: Run lint and formatting checks**

Run: `flake8 src/quads/tools/allocation_graph.py src/quads/web/blueprints/visual.py src/quads/cli/cli.py src/quads/cli/parser.py tests/tools/test_allocation_graph.py tests/web/test_allocation_graph.py tests/cli/test_regen.py`
Expected: no output.

Run: `black --check src/quads/tools/allocation_graph.py src/quads/web/blueprints/visual.py src/quads/cli/cli.py src/quads/cli/parser.py tests/tools/test_allocation_graph.py tests/web/test_allocation_graph.py tests/cli/test_regen.py`
Expected: `All done!` and no files would be reformatted.

- [ ] **Step 3: Run the CLI regeneration test when the tox API server is available**

Run: `pytest tests/cli/test_regen.py::TestRegen::test_regen_graph -v`
Expected: PASS.

- [ ] **Step 4: Commit the spec and plan**

```bash
git add docs/superpowers/specs/2026-11-11-allocation-graphic-design.md docs/superpowers/plans/2026-11-11-allocation-graphic.md
git commit -m "docs: add allocation graphic design and plan"
```
