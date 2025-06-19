import logging
import unittest
from unittest.mock import patch

from quads.tools.logger import ColorFormatter


class TestColorFormatter(unittest.TestCase):
    @patch("sys.stdout.isatty")
    def test_format_tty(self, mock_isatty):
        mock_isatty.return_value = True
        log_record = logging.LogRecord("TestLogger", logging.DEBUG, "test.py", 42, "Debug message", None, None)
        formatted_output = ColorFormatter().format(log_record)
        assert formatted_output == "\x1b[32;21mDebug message\x1b[0m"

    @patch("sys.stdout.isatty")
    def test_format_not_tty(self, mock_isatty):
        mock_isatty.return_value = False
        log_record = logging.LogRecord("TestLogger", logging.DEBUG, "test.py", 42, "Debug message", None, None)
        formatted_output = ColorFormatter().format(log_record)
        assert formatted_output == "Debug message"
