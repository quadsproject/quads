# Lab Allocation Graphic Design

Date: 2026-11-11
Issue: https://github.com/quadsproject/quads/issues/105

## Intent

QUADS should automatically produce a visual allocation graphic covering the
previous, current, and next month. Each lab allocation must appear as a block
whose vertical size reflects the number of machines in the allocation and
whose horizontal size reflects the allocation duration. Each block must show
the allocation description, the ticket number as a link to the request, and a
list of machine types with counts.

The existing `/visual` heatmap is a per-host/per-day grid. It does not show
allocation duration or machine counts as block dimensions, so it does not
satisfy the issue.

## Goals

- Generate one graphic for a three-month window (previous, current, next
  month) from live QUADS data.
- Render allocation blocks with duration-based width and machine-count-based
  height.
- Include description, ticket link, and machine model counts in each block.
- Regenerate automatically through the existing visualization workflow.
- Keep the implementation dependency-free and testable.

## Non-goals

- Changing the existing per-host heatmap.
- Adding a database migration.
- Exporting a raster image (PNG/JPEG); the browser can print/screenshot the
  page.
- Interactive editing of allocations.

## Constraints

- Python 3.11+, Flask, Jinja2, existing QUADS API client.
- No new runtime dependencies.
- Must use the existing `visual_web_dir`, `ticket_url`, and `ticket_queue`
  configuration.
- Must not break the existing `/visual` routes or `--regen-heatmap`.

## Approaches Considered

1. **Pure-Python SVG generator.** Dependency-free, clickable ticket links,
   text inside blocks, easy to serve. Tradeoff: manual text wrapping and
   clipping; a vector file rather than a page.
2. **HTML/CSS absolute-positioned blocks (chosen).** Easiest text wrapping,
   hover details, and consistency with the existing `/visual` page. Tradeoff:
   it is a web page, not a standalone image file.
3. **matplotlib PNG.** Conventional chart output. Tradeoff: new dependency,
   awkward rich text and non-clickable ticket links, fixed resolution.

The HTML/CSS approach was selected because the requirement is a readable,
information-dense graphic, and the existing web stack already serves generated
HTML fragments from `visual_web_dir`.

## Design

### Data flow

A new tool, `quads.tools.allocation_graph`, uses the existing `QuadsApi` client
to fetch:

- `schedules/hosts_range` for the three-month window, which returns
  per-host schedules with assignment id, start, end, cloud, description,
  owner, and ticket.
- `hosts?retired=False&broken=False` for host metadata, including model and
  host type.

The tool aggregates schedules by assignment id, merges overlapping schedules
for the same assignment, counts hosts, groups hosts by model, and clips block
geometry to the visible window. Ticket links are built as
`{ticket_url}/{ticket_queue}-{ticket}`, matching the existing web templates.

### Rendering

`render_allocations(allocations, window_start, window_end, generated_at)` is a
pure function returning an HTML fragment:

- A header with the window and generation timestamp.
- A timeline with day/month grid lines and month labels.
- Blocks stacked in start-time order; each block's height is proportional to
  its machine count, proportional up to a fixed maximum height.
- Each block contains the description, a ticket link, and machine model
  counts. Text is escaped with `html.escape`. A `title` attribute carries the
  full details for narrow blocks.
- A legend mapping colors to clouds.

The fragment is written to
`{visual_web_dir}/allocation-graphic.html`.

### Web integration

- New route `GET /visual/graph` reads the generated fragment and renders it
  inside a new `wiki/allocation_graph.html` template.
- Add an "Allocation Graphic" item to the Visuals navbar.
- Return 404 with a clear message when the fragment has not been generated.

### CLI integration

- New `--regen-graph` action in the argument parser, wired to
  `QuadsCli.action_regen_graph`, which calls the tool and logs success.
- Add a commented cron entry next to `--regen-heatmap`.

### Tests

- Unit tests for aggregation, clipping, block sizing, HTML escaping, ticket
  link construction, and empty-data behavior. These do not require a running
  API server.
- A CLI regeneration test in `tests/cli/test_regen.py` following the existing
  `test_regen_heatmap` pattern.
- A web route test if the existing web test setup supports it.

### Documentation

- Add the command to the README cron command table.
- Add an "Allocation Graphic" example to `docs/quads-workflow.md`.

## Builder Notes

- Follow the existing `simple_table_generator.py` conventions for API access
  and file output.
- Keep the renderer pure and injectable so tests can pass fixture data without
  HTTP.
- Do not embed a full HTML document in the fragment; the web template owns the
  document structure.
- If an allocation spans beyond the window, clip the block and indicate the
  clipping in the tooltip.
