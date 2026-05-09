#! /usr/bin/env python

import argparse
import logging

import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Column, Table

from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest

logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
logger = logging.getLogger(__name__)
quads = QuadsApi(Config)


def import_current_schedules(filepath):

    with open(filepath, "r") as infile:
        data = yaml.safe_load(infile)

    clouds = data["clouds"]
    schedules = data["current_schedules"]

    with Progress(SpinnerColumn(), TextColumn("{task.description}", table_column=Column(min_width=30)), BarColumn(), MofNCompleteColumn()) as progress:
        task = progress.add_task("Importing clouds", total=len(clouds))
        for cloud_name, properties in clouds.items():
            progress.update(task, description=f"[cyan]{cloud_name}[/]")
            data = {
                "cloud": cloud_name,
                "description": properties["description"],
                "owner": properties["owner"],
                "ccuser": properties["ccuser"],
                "qinq": properties["qinq"],
                "ticket": properties["ticket"],
                "wipe": properties["wipe"],
            }

            cloud_obj = quads.get_cloud(cloud_name)
            if not cloud_obj:
                quads.insert_cloud(data)

            active_assignment = quads.get_active_cloud_assignment(cloud_name)
            if not active_assignment:
                quads.insert_assignment(data)
            else:
                logger.info(f"Cloud {cloud_name} already has an active assignment.")
            progress.advance(task)

    imported_rows = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}", table_column=Column(min_width=30)), BarColumn(), MofNCompleteColumn()) as progress:
        task = progress.add_task("Importing schedules", total=len(schedules))
        for schedule in schedules:
            progress.update(task, description=f"[cyan]{schedule.get('host', '')}[/]")
            try:
                quads.get_host(schedule["host"])
            except (APIServerException, APIBadRequest):
                logger.info(f"Undefined host: {schedule['host']}. SKIPPING")
                progress.advance(task)
                continue

            format_str = "%Y-%m-%d %H:%M"
            _start = schedule["start"].strftime(format_str)
            _end = schedule["end"].strftime(format_str)
            _build_start = schedule["build_start"].strftime(format_str) if schedule["build_start"] else None
            _build_end = schedule["build_end"].strftime(format_str) if schedule["build_end"] else None

            schedule_data = {
                "cloud": schedule["cloud"],
                "hostname": schedule["host"],
                "start": _start,
                "end": _end,
                "build_start": _build_start,
                "build_end": _build_end,
            }
            quads.insert_schedule(schedule_data)
            imported_rows.append((schedule["cloud"], schedule["host"], _start, _end))

            if schedule["moved"]:
                quads.update_host(schedule["host"], {"cloud": schedule["cloud"]})
            progress.advance(task)

    if imported_rows:
        console = Console()
        if console.is_terminal:
            table = Table(title="Imported Schedules", show_header=True, header_style="bold cyan")
            table.add_column("Cloud", style="cyan")
            table.add_column("Host")
            table.add_column("Start")
            table.add_column("End")
            for row in imported_rows:
                table.add_row(*row)
            console.print(table)
        else:
            for cloud, host, start, end in imported_rows:
                print(f"{cloud}\t{host}\t{start}\t{end}")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Import current schedules from a YAML file.")
    parser.add_argument("--input", type=str, help="The name of the input file.", required=True)
    args = parser.parse_args()
    import_current_schedules(args.input)
