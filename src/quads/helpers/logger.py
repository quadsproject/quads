import logging
import sys
from pathlib import Path


class LoggingManager:
    """
    Centralized logging manager for QUADS
    Provides consistent logging configuration across all modules
    """

    # Map of module names to their specific log files (based on cron configuration)
    MODULE_LOG_FILES = {
        "quads.tools.move_and_rebuild": "/var/log/move-and-rebuild.log",
        "quads.tools.validate_env": "/var/log/validate-env.log",
        "quads.tools.notify": "/var/log/quads-notify.log",
        "quads.tools.notify_tenant": "/var/log/quads-notify.log",
        "quads.tools.reports": "/var/log/quads-reports.log",
        "quads.tools.foreman_heal": "/var/log/quads-foreman.log",
    }

    def __init__(self, config=None):
        self.config = config
        self._loggers = {}

    def get_logger(self, name, log_file=None, level=logging.INFO, use_color=None, force_terminal=None):
        """
        Get or create a logger with consistent configuration

        Args:
            name: Logger name (typically __name__)
            log_file: Optional log file path (uses module-specific or config default)
            level: Logging level (default INFO)
            use_color: Force color on/off (auto-detects TTY if None)
            force_terminal: Force terminal output even when redirected (default: auto-detect TTY)
        """
        if name in self._loggers:
            return self._loggers[name]

        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Clear any existing handlers to avoid duplicates
        logger.handlers.clear()

        # Determine if we should show terminal output
        # Always show on terminal when TTY is available, or when explicitly forced
        show_terminal = sys.stdout.isatty() or (force_terminal is True)

        # Add console handler if we should show terminal output
        if show_terminal:
            console_handler = logging.StreamHandler(sys.stdout)
            if use_color is None:
                use_color = sys.stdout.isatty()

            if use_color:
                console_formatter = ColorFormatter()
            else:
                # Use standard format from config if available
                fmt = getattr(self.config, "STDFMT", "%(levelname)s - %(message)s")
                console_formatter = logging.Formatter(fmt)

            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        # Determine log file - check module-specific first, then provided, then config default
        if not log_file:
            # Check if this module has a specific log file
            log_file = self.MODULE_LOG_FILES.get(name)

        if not log_file and self.config and hasattr(self.config, "log"):
            log_file = self.config.log

        # Always add file handler if log file is available
        if log_file:
            try:
                # Ensure log directory exists
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                file_handler = logging.FileHandler(log_file)
                # Use detailed format for file logging
                fmt = getattr(self.config, "LOGFMT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                file_formatter = logging.Formatter(fmt)
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
            except (OSError, PermissionError) as e:
                # Only warn if we have terminal output, otherwise silently continue
                if show_terminal:
                    logger.warning(f"Could not create log file {log_file}: {e}")

        # Prevent propagation to root logger to avoid duplicate messages
        logger.propagate = False

        self._loggers[name] = logger
        return logger

    def set_level(self, level):
        """Set logging level for all managed loggers"""
        for logger in self._loggers.values():
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)

    def get_request_logger(self, name, request_id=None):
        """Get a logger with request context for API/web requests"""
        logger = self.get_logger(name)
        if request_id:
            # Create a LoggerAdapter to add request_id to all messages
            return RequestContextAdapter(logger, {"request_id": request_id})
        return logger

    def get_tool_logger(self, name, level=logging.INFO):
        """
        Get a logger specifically configured for QUADS tools
        This ensures both file logging and terminal output for interactive use
        """
        return self.get_logger(name, level=level, force_terminal=True)


class RequestContextAdapter(logging.LoggerAdapter):
    """Adapter to add request context to log messages"""

    def process(self, msg, kwargs):
        request_id = self.extra.get("request_id")
        if request_id:
            return f"[{request_id}] {msg}", kwargs
        return msg, kwargs


class ColorFormatter(logging.Formatter):
    """
    Logging Formatter to add colors and count warning / errors
    """

    grey = "\x1b[38;21m"
    yellow = "\x1b[33;21m"
    green = "\x1b[32;21m"
    red = "\x1b[31;21m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_msg = "%(message)s"
    detailed_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: green + format_msg + reset,
        logging.INFO: format_msg,
        logging.WARNING: yellow + format_msg + reset,
        logging.ERROR: red + format_msg + reset,
        logging.CRITICAL: bold_red + format_msg + reset,
    }

    def __init__(self, use_detailed=False):
        super().__init__()
        self.use_detailed = use_detailed

    def format(self, record):
        if sys.stdout.isatty():
            log_fmt = self.FORMATS.get(record.levelno)
        else:
            log_fmt = self.detailed_format if self.use_detailed else self.format_msg
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
