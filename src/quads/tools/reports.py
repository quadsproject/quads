from quads.config import Config
from quads.helpers.utils import (
    date_span,
    first_day_month,
    last_day_month,
    month_delta_past,
)
from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table

from quads.quads_api import QuadsApi

quads = QuadsApi(Config)
console = Console()


def report_available(_start, _end):
    start = _start.replace(hour=22, minute=0, second=0)
    end = _end.replace(hour=22, minute=0, second=0)
    next_sunday = start + timedelta(days=(6 - start.weekday()))

    hosts = quads.filter_hosts({"retired": False, "broken": False})

    days = 0
    total_allocated_month = 0
    total_hosts = len(hosts)
    for _date in date_span(start, end):
        total_allocated_month += len(quads.get_current_schedules({"date": _date.strftime("%Y-%m-%dT%H:%M")}))
        days += 1
    utilized = total_allocated_month * 100 // (total_hosts * days)

    console.print(f"[bold]QUADS report for {start.date()} to {end.date()}[/bold]")
    console.print(f"Percentage Utilized: [cyan]{utilized}%[/cyan]")

    average_build = quads.get_average_build_delta()
    if average_build is not None:
        console.print(f"Average build delta: [cyan]{average_build}[/cyan]")

    now = datetime.now()
    avail_start = next_sunday + timedelta(minutes=1)
    two_week_end = next_sunday + timedelta(weeks=2)
    four_week_end = next_sunday + timedelta(weeks=4)

    _fmt = "%Y-%m-%dT%H:%M"
    summary = quads.get_availability_summary(
        {
            "now": now.strftime(_fmt),
            "two_week_start": avail_start.strftime(_fmt),
            "two_week_end": two_week_end.strftime(_fmt),
            "four_week_end": four_week_end.strftime(_fmt),
        }
    )

    table = Table(title="Availability Summary", show_header=True, header_style="bold cyan")
    table.add_column("Server Type", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Free", justify="right")
    table.add_column("Scheduled", justify="right")
    table.add_column("2 weeks", justify="right")
    table.add_column("4 weeks", justify="right")

    for row in summary:
        total = row["total"]
        scheduled_count = row["scheduled"]
        free = total - scheduled_count
        schedule_percent = scheduled_count * 100 // total
        table.add_row(
            row["model"],
            str(total),
            str(free),
            f"{schedule_percent}%",
            str(row["avail_2w"]),
            str(row["avail_4w"]),
        )

    console.print(table)


def report_scheduled(months, year):
    table = Table(title="Scheduled Report", show_header=True, header_style="bold cyan")
    table.add_column("Month", style="cyan")
    table.add_column("Scheduled", justify="right")
    table.add_column("Systems", justify="right")
    table.add_column("% Utilized", justify="right")

    now = datetime.now()
    now = now.replace(year=year, hour=22, minute=0, second=0)
    if months:
        for month in range(months):
            _add_scheduled_row(table, month, now)
    else:
        _add_scheduled_row(table, months, now)

    console.print(table)


def _add_scheduled_row(table, month, now):
    _date = now
    if month > 0:
        _date = month_delta_past(now, month)
    start = first_day_month(_date)
    end = last_day_month(_date)
    _fmt = "%Y-%m-%dT%H:%M"
    stats = quads.get_utilization_stats({"start": start.strftime(_fmt), "end": end.strftime(_fmt)})

    hosts = stats["hosts"]
    days = stats["days"]
    utilization = 0
    if hosts and days:
        utilization = stats["scheduled_count"] * 100 // (days * hosts)
    f_month = f"{start.month:02}"
    table.add_row(
        f"{start.year}-{f_month}",
        str(stats["schedules"]),
        str(hosts),
        f"{utilization}%",
    )


def report_detailed(_start, _end):
    start = _start.replace(hour=21, minute=59, second=0)
    end = _end.replace(hour=22, minute=1, second=0)
    payload = {
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "end": end.strftime("%Y-%m-%dT%H:%M"),
    }
    schedules = quads.get_schedules(payload)

    table = Table(title="Detailed Report", show_header=True, header_style="bold cyan")
    table.add_column("Owner", style="cyan")
    table.add_column("Ticket", justify="right")
    table.add_column("Cloud", justify="right")
    table.add_column("Description")
    table.add_column("Systems", justify="right")
    table.add_column("Scheduled", justify="right")
    table.add_column("Duration", justify="right")

    for schedule in schedules:
        if schedule:
            delta = schedule.end - schedule.start
            description = schedule.assignment.description[:10]
            table.add_row(
                schedule.assignment.owner,
                schedule.assignment.ticket,
                schedule.assignment.cloud.name,
                description,
                str(len(schedules)),
                str(schedule.start)[:10],
                str(delta.days),
            )

    console.print(table)


if __name__ == "__main__":  # pragma: no cover
    _start = first_day_month(datetime.now())
    _end = last_day_month(datetime.now())
    report_available(_start, _end)

    _months = datetime.now().month
    _year = datetime.now().year
    report_scheduled(_months, _year)
