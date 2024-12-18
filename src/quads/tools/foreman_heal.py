#!/usr/bin/env python3

from quads.config import Config
from quads.quads_api import QuadsApi
from quads.tools.external.foreman import Foreman

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.propagate = False
logging.basicConfig(level=logging.INFO, format="%(message)s")

quads = QuadsApi(Config)


def rbac(_logger=None):
    global logger
    if _logger:  # pragma: no cover
        logger = _logger

    loop = asyncio.get_event_loop()

    foreman_admin = Foreman(
        Config["foreman_api_url"],
        Config["foreman_username"],
        Config["foreman_password"],
    )

    ignore = [Config["spare_pool_name"]]
    if Config.foreman_rbac_exclude:  # pragma: no cover
        ignore.extend(Config.foreman_rbac_exclude.split("|"))
    clouds = quads.get_clouds()
    for cloud in clouds:
        ass = quads.get_active_cloud_assignment(cloud.name)
        if ass:
            infra_pass = f"{Config['infra_location']}@{ass.ticket}"
            loop.run_until_complete(foreman_admin.update_user_password(cloud.name, infra_pass))

            foreman_cloud_user = Foreman(
                Config["foreman_api_url"],
                cloud.name,
                infra_pass,
            )

            if cloud.name not in ignore:
                logger.info(f"Processing {cloud.name}")

                cloud_hosts = loop.run_until_complete(foreman_cloud_user.get_all_hosts())

                user_id = loop.run_until_complete(foreman_admin.get_user_id(cloud.name))
                admin_id = loop.run_until_complete(foreman_admin.get_user_id(Config["foreman_username"]))

                current_schedule = quads.get_current_schedules({"cloud": cloud.name})
                if current_schedule:

                    logger.info("  Current Host Permissions:")
                    for host, _ in cloud_hosts.items():  # pragma: no cover
                        logger.info(f"    {host}")

                        match = [schedule.host.name for schedule in current_schedule if schedule.host.name == host]
                        if not match:
                            _host_id = loop.run_until_complete(foreman_admin.get_host_id(host))
                            loop.run_until_complete(foreman_admin.put_element("hosts", _host_id, "owner_id", admin_id))
                            logger.info(f"* Removed permission {host}")

                    for schedule in current_schedule:
                        match = [host for host, _ in cloud_hosts.items() if host == schedule.host.name]
                        if not match:
                            # want to run these separately to avoid ServerDisconnect
                            _host_id = loop.run_until_complete(foreman_admin.get_host_id(schedule.host.name))
                            loop.run_until_complete(foreman_admin.put_element("hosts", _host_id, "owner_id", user_id))
                            logger.info(f"* Added permission {schedule.host.name}")
                else:
                    if cloud_hosts:  # pragma: no cover
                        logger.info("  No active schedule, removing pre-existing roles.")
                        for host, _ in cloud_hosts.items():
                            _host_id = loop.run_until_complete(foreman_admin.get_host_id(host))
                            loop.run_until_complete(foreman_admin.put_element("hosts", _host_id, "owner_id", admin_id))
                            logger.info(f"* Removed permission {host}")
                    else:
                        logger.info("  No active schedule nor roles assigned.")


if __name__ == "__main__":  # pragma: no cover
    rbac()
