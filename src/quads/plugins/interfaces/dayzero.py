from abc import abstractmethod
from quads.plugins.base import BasePlugin

RUN_MODE_PER_HOST = "per_host"
RUN_MODE_PER_CLOUD = "per_cloud"


class DayzeroPlugin(BasePlugin):
    """Interface for post-release day-zero actions on provisioned hosts.

    Set run_mode at the class level:
      - "per_host": execute() is called once per host with a single hostname
        and schedule_data dict.
      - "per_cloud": execute() is called once per cloud with a list of
        hostnames and a list of schedule_data dicts.
    """

    run_mode: str = RUN_MODE_PER_CLOUD

    @abstractmethod
    async def execute(self, host, cloud: str, schedule_data) -> bool:
        pass
