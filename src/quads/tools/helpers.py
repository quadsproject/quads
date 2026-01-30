import asyncio
from typing import Union


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Returns the current event loop.
    In Python 3.10+, get_event_loop() raises RuntimeError if no loop is set
    in the current thread. This helper catches that, creates a new loop,
    sets it, and returns it.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop


def strtobool(value: Union[str, int, bool]) -> bool:
    """
    Converts a string representation of truth to True (1) or False (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'.
    """
    return str(value).lower() in ("y", "yes", "t", "true", "on", "1")
