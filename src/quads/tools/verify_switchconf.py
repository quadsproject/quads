#!/usr/bin/env python3

import argparse
import logging

from quads.tools.external.switch import Switch

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def main(cloud: str, host: str, change: bool):
    switch = Switch(logger)
    switch.verify(host, cloud, change)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Verify switch configs for a cloud or host")
    parser.add_argument(
        "--cloud",
        dest="cloud",
        type=str,
        default=None,
        help="Cloud name to verify switch configuration for.",
    )
    parser.add_argument(
        "--host",
        dest="host",
        type=str,
        default=None,
        help="Host name to verify switch configuration for.",
    )
    parser.add_argument("--change", dest="change", action="store_true", help="Commit changes on switch.")

    args = parser.parse_args()
    main(args.cloud, args.host, args.change)
