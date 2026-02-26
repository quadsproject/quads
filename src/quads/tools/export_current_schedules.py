#! /usr/bin/env python

import argparse
import logging

import yaml

from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
quads = QuadsApi(Config)


def export_current_schedules(output):
    current_schedules = []
    clouds = {}
    try:
        future_schedules = quads.get_future_schedules()
    except (APIServerException, APIBadRequest) as e:
        logger.error(f"Failed to get future schedules: {e}")
        return
    for schedule in future_schedules:
        cloud = schedule.assignment.cloud
        if cloud.name not in clouds:
            clouds[cloud.name] = cloud.as_dict()
        _build_start = schedule.build_start if schedule.build_start else None
        _build_end = schedule.build_end if schedule.build_end else None
        current_schedules.append(
            {
                "cloud": cloud.name,
                "host": schedule.host.name,
                "start": schedule.start,
                "end": schedule.end,
                "build_start": _build_start,
                "build_end": _build_end,
                "moved": schedule.host.cloud.name != schedule.host.default_cloud.name,
            }
        )

    data = {"clouds": clouds, "current_schedules": current_schedules}

    with open(output, "w+") as outfile:
        yaml.dump(data, outfile, default_flow_style=False)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Export current schedules to a YAML file.")
    parser.add_argument("--output", type=str, help="The name of the output file.", required=True)
    args = parser.parse_args()
    export_current_schedules(args.output)
