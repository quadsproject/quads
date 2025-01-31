#! /usr/bin/env python

import argparse
import logging

import yaml

from quads.config import Config
from quads.exceptions import APIBadRequest, APIServerException
from quads.quads_api_proxy import QuadsApiProxy as QuadsApi

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
quads = QuadsApi(Config)


def import_current_schedules(filepath):

    with open(filepath, "r") as infile:
        data = yaml.safe_load(infile)

    clouds = data["clouds"]
    schedules = data["current_schedules"]

    for cloud_name, properties in clouds.items():
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

    for schedule in schedules:
        try:
            quads.get_host(schedule["host"])
        except (APIServerException, APIBadRequest):
            logger.info(f"Undefined host: {schedule['host']}. SKIPPING")
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

        if schedule["moved"]:
            quads.update_host(schedule["host"], {"cloud": schedule["cloud"]})


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Import current schedules from a YAML file.")
    parser.add_argument("--input", type=str, help="The name of the input file.", required=True)
    args = parser.parse_args()
    import_current_schedules(args.input)
