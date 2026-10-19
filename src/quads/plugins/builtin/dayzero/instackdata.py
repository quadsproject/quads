import asyncio
import os

from quads.config import Config
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.quads_api import QuadsApi
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException

REMOTE_DIR = "/root"
INSTACK_FILES = ("instackenv", "ocpinventory")


class InstackDataPlugin(DayzeroPlugin):
    name = "instackdata"
    version = "1.0.0"
    description = "Copy generated instack inventory files to first host"
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

        try:
            files = self._read_files(cloud)
        except OSError as e:
            self.logger.error(f"Failed to read instack files for {cloud}: {e}")
            return False
        if not files:
            self.logger.info(f"No instack files for {cloud}, skipping")
            return True

        first_host = current_schedules[0].host.name
        self.logger.info(f"Copying {', '.join(files)} to {first_host} for {cloud}")

        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, self._deliver_files, first_host, files)
        except Exception as e:
            self.logger.error(f"Failed to copy instack files to {first_host}: {e}")
            return False

    def _read_files(self, cloud):
        files = {}
        for name in INSTACK_FILES:
            filename = f"{cloud}_{name}.json"
            path = os.path.join(Config["json_web_path"], filename)
            if os.path.isfile(path):
                with open(path) as _file:
                    files[filename] = _file.read()
        return files

    def _deliver_files(self, host, files) -> bool:
        try:
            ssh = SSHHelper(host)
        except SSHHelperException as e:
            self.logger.error(f"SSH to {host} failed: {e}")
            return False

        try:
            for filename, content in files.items():
                remote_path = os.path.join(REMOTE_DIR, filename)
                if not ssh.put_file(content, remote_path):
                    self.logger.error(f"Failed to copy {filename} to {host}")
                    return False
            return True
        finally:
            ssh.disconnect()
