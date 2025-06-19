import asyncio


def get_running_loop() -> asyncio.AbstractEventLoop:
    loop = asyncio.get_event_loop()
    if not loop.is_running():  # pragma: no cover
        raise RuntimeError("The object should be created within an async function")
    return loop


def strtobool(value: str) -> bool:
    value = value.lower()
    if value in ("y", "yes", "on", "1", "true", "t"):
        return True
    return False
