#!/usr/bin/env python3
# This file is part of QUADs.
#
# QUADS is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# QUADS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with QUADs.  If not, see <http://www.gnu.org/licenses/>.

import argcomplete
import logging
import os
import signal
import sys
from typing import Optional

from quads.cli import parser, QuadsCli
from quads.config import Config, DEFAULT_CONF_PATH, logging_manager
from quads.exceptions import CliException
from quads.quads_api import QuadsApi


def main(_logger: logging = None) -> Optional[int]:
    argcomplete.autocomplete(parser)
    cli_args: dict = vars(parser.parse_args())

    # Use centralized logging manager
    log_level = logging.DEBUG if cli_args.get("debug", False) else logging.INFO
    _logger = logging_manager.get_logger(__name__, level=log_level, use_color=True)

    _logger.debug("Attached to terminal, making logs colorful")

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    Config.load_from_yaml(DEFAULT_CONF_PATH)

    sys.path.append(os.path.dirname(__file__) + "/../")

    quads = QuadsApi(config=Config)

    qcli = QuadsCli(
        quads=quads,
        logger=_logger,
    )

    try:
        _exit_code = qcli.run(
            action=cli_args.get("action"),
            cli_args=cli_args,
        )
    except CliException as exc:
        _logger.error(str(exc))
        _exit_code = 2

    return _exit_code


if __name__ == "__main__":
    exit_code: Optional[int] = None

    try:
        exit_code = main()
    except Exception as exc:
        # Create a basic logger for unhandled exceptions
        basic_logger = logging_manager.get_logger(__name__)
        basic_logger.exception(exc, exc_info=exc)
        exit_code = 1

    exit(0 if exit_code is None else exit_code)
