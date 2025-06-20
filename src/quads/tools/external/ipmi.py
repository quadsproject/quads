import asyncio
import logging
from typing import List, Optional

from quads.config import Config

logger = logging.getLogger(__name__)


class IPMI:
    def __init__(
        self,
        host: str,
        username: str = Config["ipmi_username"],
        password: str = Config["ipmi_password"],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.logger: Optional[logging.Logger] = logger
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(20)

    @classmethod
    async def create(cls, host: str, username: str, password: str) -> "IPMI":
        ipmi = cls(host, username, password)
        return ipmi

    async def execute(self, arguments: List[str]) -> None:  # pragma: no cover
        ipmi_cmd = [
            "/usr/bin/ipmitool",
            "-I",
            "lanplus",
            "-H",
            f"mgmt-{self.host}",
            "-U",
            self.username,
            "-P",
            self.password,
        ]
        self.logger.debug(f"Executing IPMI with argmuents: {arguments}")
        cmd = ipmi_cmd + arguments
        async with self.semaphore:
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            self.logger.debug(f"{stdout.decode().strip()}")

    async def reset(self) -> None:  # pragma: no cover
        ipmi_off = [
            "chassis",
            "power",
            "off",
        ]
        await self.execute(ipmi_off)
        await asyncio.sleep(Config["ipmi_reset_sleep"])
        ipmi_on = [
            "chassis",
            "power",
            "on",
        ]
        await self.execute(ipmi_on)

    async def configure_user(self, user_id: int, password: str) -> bool:
        try:
            # Set password
            await self.execute(["user", "set", "password", str(user_id), password])

            # Set operator privileges
            await self.execute(["user", "priv", str(user_id), "0x4"])

            return True
        except Exception as ex:
            self.logger.error(f"Failed to configure IPMI user for {self.host}: {ex}")
            return False

    async def pxe_persistent(self) -> bool:
        try:
            await self.execute(["chassis", "bootdev", "pxe", "options=persistent"])
            await self.reset()
            return True
        except Exception as ex:
            self.logger.error(f"Failed to set PXE boot for {self.host}: {ex}")
            return False
