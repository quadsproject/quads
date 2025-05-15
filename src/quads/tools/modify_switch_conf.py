#!/usr/bin/env python3

import argparse
import logging

from quads.config import Config
from quads.quads_api import QuadsApi
from quads.tools.external.switch import Switch

quads = QuadsApi(Config)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def main(host: str, change: bool, nic1: str, nic2: str, nic3: str, nic4: str, nic5: str):
    switch = Switch(logger)
    switch.modify(host, change, nic1, nic2, nic3, nic4, nic5)


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Verify switch configs for a cloud or host")
    parser.add_argument(
        "--host",
        dest="host",
        type=str,
        default=None,
        help="Host name to verify switch configuration for.",
        required=True,
    )
    parser.add_argument(
        "--nic1",
        dest="nic1",
        type=str,
        default=None,
        help="Nic 1 (EM1).",
    )
    parser.add_argument(
        "--nic2",
        dest="nic2",
        type=str,
        default=None,
        help="Nic 2 (EM2).",
    )
    parser.add_argument(
        "--nic3",
        dest="nic3",
        type=str,
        default=None,
        help="Nic 3 (EM3).",
    )
    parser.add_argument(
        "--nic4",
        dest="nic4",
        type=str,
        default=None,
        help="Nic 4 (EM4).",
    )
    parser.add_argument(
        "--nic5",
        dest="nic5",
        type=str,
        default=None,
        help="Nic 5 (EM5).",
    )
    parser.add_argument("--change", dest="change", action="store_true", help="Commit changes on switch.")

    args = parser.parse_args()
    main(args.host, args.change, args.nic1, args.nic2, args.nic3, args.nic4, args.nic5)
