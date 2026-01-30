import asyncio


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Returns the current event loop.
    In Python 3.10+, get_event_loop() raises RuntimeError if no loop is set
    in the current thread. This helper catches that, creates a new loop,
    sets it, and returns it.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


def get_running_loop() -> asyncio.AbstractEventLoop:
    try:
        loop = asyncio.get_event_loop()
        if not loop.is_running():
            raise RuntimeError("The object should be created within an async function")
        return loop
    except RuntimeError:
        raise RuntimeError("The object should be created within an async function")


def strtobool(value: str) -> bool:
    return str(value).lower() in ("y", "yes", "t", "true", "on", "1")
