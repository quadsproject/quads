import asyncio


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Returns the current event loop.
    In Python 3.10+, get_event_loop() raises RuntimeError if no loop is set
    in the current thread. This helper catches that, creates a new loop,
    sets it, and returns it.
    """
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def get_running_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():  # pragma: no cover
            raise RuntimeError("The object should be created within an async function")
        return loop
    except RuntimeError:
        # Re-raise as the specific error expected by callers if no loop exists
        raise RuntimeError("The object should be created within an async function")


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "on", "1", "true", "t"):
        return True
    return False
