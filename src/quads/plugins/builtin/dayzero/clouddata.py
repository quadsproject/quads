import asyncio
import base64
import logging

import yaml

from quads.config import Config
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.quads_api import QuadsApi
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException

logger = logging.getLogger(__name__)

REMOTE_PATH = "/root/quads_env.yml"


class CloudDataPlugin(DayzeroPlugin):
    name = "clouddata"
    version = "1.0.0"
    description = "Generate QUADS environment datafile on first host"
    author = "QUADS Team"
    run_mode = "per_cloud"

    def initialize(self, plugin_manager=None) -> bool:
        return True

    async def execute(self, cloud) -> bool:
        quads = QuadsApi(Config)
        assignment = quads.get_active_cloud_assignment(cloud)
        if not assignment:
            self.logger.info(f"No active assignment for {cloud}, skipping")
            return True

        current_schedules = quads.get_current_schedules({"cloud": cloud})
        if not current_schedules:
            self.logger.info(f"No current schedules for {cloud}, skipping")
            return True

        hosts = sorted(sched.host.name for sched in current_schedules)
        first_host = current_schedules[0].host.name

        env_data = {
            "cloud_name": assignment.cloud.name,
            "assignment_id": assignment.id,
            "bmc_user": Config["ipmi_cloud_username"],
            "bmc_pass": f"{Config['infra_location']}@{assignment.ticket}",
            "cloud_systems": hosts,
            "cloud_ticket": f"{Config.get('ticket_url', '')}/{assignment.ticket}",
        }

        content = yaml.dump(env_data, default_flow_style=False, sort_keys=False)

        self.logger.info(f"Deploying {REMOTE_PATH} to {first_host} for {cloud}")

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, self._deliver_file, first_host, content
            )
        except Exception as e:
            self.logger.error(f"Failed to deploy {REMOTE_PATH} to {first_host}: {e}")
            return False

        return result

    def _deliver_file(self, host, content):
        try:
            ssh = SSHHelper(host)
            encoded = base64.b64encode(content.encode()).decode()
            cmd = (
                f"echo '{encoded}' | base64 -d > {REMOTE_PATH} && "
                f"chmod 644 {REMOTE_PATH}"
            )
            result, _ = ssh.run_cmd(cmd)
            ssh.disconnect()
            return result
        except SSHHelperException as e:
            self.logger.error(f"SSH to {host} failed: {e}")
            return False
