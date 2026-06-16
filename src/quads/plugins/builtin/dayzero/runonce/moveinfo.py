import asyncio
import logging
from typing import Optional
from quads.plugins.interfaces.dayzero import DayzeroPlugin

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "pending",
    "switch_config",
    "ipmi_config",
    "hardware_prep",
    "power_on",
    "provisioning",
    "cleanup",
    "reboot",
    "post_install",
    "foreman_rbac",
    "validation",
    "released",
]

DEPLOY_FILE = "/root/quads_deployed.txt"
SSH_TIMEOUT = 30


class MoveInfoPlugin(DayzeroPlugin):
    name = "moveinfo"
    version = "1.0.0"
    description = "Write move stage timestamps to /root/quads_deployed.txt on released hosts"
    author = "QUADS Team"
    run_mode = "per_host"

    def initialize(self, plugin_manager=None) -> bool:
        self.logger.info("moveinfo plugin initialized")
        return True

    async def execute(self, host: str, cloud: str, schedule_data: dict) -> bool:
        timestamps = schedule_data.get("stage_timestamps", {})
        content = self._build_content(host, cloud, timestamps)

        try:
            return await self._write_to_host(host, content)
        except Exception as e:
            self.logger.error(f"Failed to write {DEPLOY_FILE} on {host}: {e}")
            return False

    def _build_content(self, host: str, cloud: str, timestamps: dict) -> str:
        lines = [
            "QUADS Deployment Info",
            f"Host: {host}",
            f"Cloud: {cloud}",
            "=====================",
            "Stage Timestamps:",
        ]
        for idx, stage in enumerate(STAGE_ORDER, 1):
            ts = timestamps.get(stage, "N/A")
            lines.append(f"  {idx:02d}. {stage:<17s} : {ts}")
        lines.append("")
        return "\n".join(lines)

    async def _write_to_host(self, host: str, content: str) -> bool:
        cmd = f"cat > {DEPLOY_FILE}"
        proc = await asyncio.create_subprocess_exec(
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "BatchMode=yes",
            f"root@{host}",
            cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=content.encode()), timeout=SSH_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            self.logger.error(f"SSH to {host} timed out after {SSH_TIMEOUT}s")
            return False

        if proc.returncode != 0:
            self.logger.error(f"SSH to {host} failed (rc={proc.returncode}): {stderr.decode().strip()}")
            return False

        self.logger.info(f"Wrote {DEPLOY_FILE} on {host}")
        return True
