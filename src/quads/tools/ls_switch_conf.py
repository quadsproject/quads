#!/usr/bin/env python3

import argparse
import logging

from quads.config import Config
from quads.quads_api import QuadsApi
from quads.tools.external.switch import Switch

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
quads = QuadsApi(Config)


def main(cloud: str, all: bool):
    switch = Switch(logger)
    switch.ls_config(cloud, all)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="List switch configs for a cloud")
    parser.add_argument(
        "--cloud",
        dest="cloud",
        type=str,
        default=None,
        help="Cloud name to verify switch configuration for.",
        required=True,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="List all hosts interfaces",
    )

    args = parser.parse_args()
    try:
        main(args.cloud, args.all)
    except KeyboardInterrupt:
        pass
