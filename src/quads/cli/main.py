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
from quads.config import Config, DEFAULT_CONF_PATH
from quads.exceptions import CliException
from quads.tools.logger import ColorFormatter

logger = logging.getLogger(__name__)


def main(_logger: logging = logger) -> Optional[int]:
    stdout_stream = logging.StreamHandler(sys.stdout)
    _logger.addHandler(stdout_stream)
    _logger.propagate = False

    argcomplete.autocomplete(parser)
    cli_args: dict = vars(parser.parse_args())

    if cli_args.get("debug", False):
        _logger.setLevel(level=logging.DEBUG)
    else:
        _logger.setLevel(level=logging.INFO)

    if sys.stdout.isatty():
        stdout_stream.setFormatter(ColorFormatter())
        _logger.debug("Attached to terminal, making logs colorful")

    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    sys.path.append(os.path.dirname(__file__) + "/../")

    qcli = QuadsCli(
        logger=_logger,
    )

    try:
        _exit_code = qcli.run(
            action=cli_args.get("action"),
            cli_args=cli_args,
        )
    except CliException as exc:
        logger.error(str(exc))
        _exit_code = 2

    return _exit_code


if __name__ == "__main__":
    exit_code: Optional[int] = None

    try:
        exit_code = main(_logger=logger)
    except Exception as exc:
        logger.exception(exc, exc_info=exc)
        exit_code = 1

    exit(0 if exit_code is None else exit_code)
