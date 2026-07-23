import asyncio
import base64
import logging

from quads.config import Config
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.quads_api import QuadsApi

logger = logging.getLogger(__name__)

SSH_TIMEOUT = 30


class CloudCmdPlugin(DayzeroPlugin):
    name = "cloudcmd"
    version = "1.0.0"
    description = "Run cloud owner release command on first host via tmux"
    author = "QUADS Team"
    run_mode = "per_cloud"

    def initialize(self, plugin_manager=None) -> bool:
        self._domain = Config.get("domain", "")
        return True

    async def execute(self, cloud) -> bool:
        quads = QuadsApi(Config)
        assignment = quads.get_active_cloud_assignment(cloud)
        if not assignment:
            self.logger.info(f"No active assignment for {cloud}, skipping")
            return True

        owner = assignment.owner
        user_data = quads.get_user(email=f"{owner}@{self._domain}")
        if not user_data:
            self.logger.info(f"User {owner} not found, skipping")
            return True

        command = getattr(user_data, "release_command", None)
        if not command:
            self.logger.info(f"No release command set for {owner}, skipping")
            return True

        current_schedules = quads.get_current_schedules({"cloud": cloud})
        if not current_schedules:
            self.logger.info(f"No current schedules for {cloud}, skipping")
            return True

        first_host = current_schedules[0].host.name
        self.logger.info(f"Running release command for {owner} on {first_host} in {cloud}")

        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        tmux_cmd = "tmux new-session -d -s quads_release \\; " f"send-keys 'echo {encoded} | base64 -d | bash' Enter"

        try:
            return await self._ssh_exec(first_host, tmux_cmd)
        except Exception as e:
            self.logger.error(f"Failed to run release command on {first_host}: {e}")
            return False

    async def _ssh_exec(self, host, command) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "BatchMode=yes",
            f"root@{host}",
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SSH_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            self.logger.error(f"SSH to {host} timed out after {SSH_TIMEOUT}s")
            return False

        if proc.returncode != 0:
            self.logger.error(f"SSH to {host} failed (rc={proc.returncode}): {stderr.decode().strip()}")
            return False

        self.logger.info(f"Release command dispatched to tmux on {host}")
        return True
