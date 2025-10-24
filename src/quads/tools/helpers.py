import asyncio
import yaml
import logging

logger = logging.getLogger(__name__)


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


def read_yaml(_yaml_file):
    with open(_yaml_file, "r") as f:
        try:
            definitions = yaml.safe_load(f)
        except yaml.YAMLError as ex:
            error_message = f"Couldn't read file: {_yaml_file}"
            logger.error(error_message, exc_info=ex)
            raise Exception(error_message)
    return definitions


def get_host_types_from_yaml(_interfaces_path):
    definitions = read_yaml(_interfaces_path)
    host_types = set()
    for line in definitions:
        _split = line.split("_")
        host_types.add(_split[0])

    ordered_types = sorted(list(host_types))
    return ordered_types
