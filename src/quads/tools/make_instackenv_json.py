#!/usr/bin/env python3

import asyncio
import functools
import json
import os
import time
import pathlib
from collections import defaultdict
from distutils.util import strtobool
from datetime import datetime
from shutil import copyfile

from quads.quads_api import QuadsApi
from quads.tools.external.foreman import Foreman
from quads.config import Config

quads = QuadsApi(Config)


async def make_env_json(filename):
    foreman = Foreman(
        Config["foreman_api_url"],
        Config["foreman_username"],
        Config["foreman_password"],
    )

    cloud_list = quads.get_clouds()

    if not os.path.exists(Config["json_web_path"]):  # pragma: no cover
        os.makedirs(Config["json_web_path"])

    now = time.time()
    old_jsons = [file for file in os.listdir(Config["json_web_path"]) if ":" in file]
    for file in old_jsons:
        if os.stat(os.path.join(Config["json_web_path"], file)).st_mtime < now - Config["json_retention_days"] * 86400:
            os.remove(os.path.join(Config["json_web_path"], file))

    for cloud in cloud_list:
        host_list = quads.filter_hosts({"cloud": cloud.name})
        assignment = quads.get_active_cloud_assignment(cloud.name)
        foreman_password = Config["ipmi_password"]
        if assignment and assignment.ticket:
            foreman_password = f"{Config['infra_location']}@{assignment.ticket}"

        data = defaultdict(list)
        for host in host_list:
            if Config["foreman_unavailable"]:
                overcloud = {"result": "true"}
            else:
                overcloud = await foreman.get_host_param(host.name, "overcloud")

            if not overcloud:
                overcloud = {"result": "true"}

            if not isinstance(overcloud["result"], bool):
                try:
                    _overcloud_result = strtobool(overcloud["result"])
                except ValueError:
                    print(f"WARN: {host.name} overcloud value is not set correctly.")
                    _overcloud_result = 1
            else:
                _overcloud_result = overcloud["result"]

            if "result" in overcloud and _overcloud_result:
                mac = []
                if filename == "instackenv":
                    for interface in sorted(host.interfaces, key=lambda k: k.name):
                        if interface.pxe_boot:
                            mac.append(interface.mac_address)
                if filename == "ocpinventory":
                    mac = [interface.mac_address for interface in sorted(host.interfaces, key=lambda k: k.name)]
                data["nodes"].append(
                    {
                        "name": host.name,
                        "pm_password": foreman_password,
                        "pm_type": "pxe_ipmitool",
                        "mac": mac,
                        "cpu": "2",
                        "memory": "1024",
                        "disk": "20",
                        "arch": "x86_64",
                        "pm_user": Config["ipmi_cloud_username"],
                        "pm_addr": "mgmt-%s" % host.name,
                    }
                )

        content = json.dumps(data, indent=4, sort_keys=True)

        if not os.path.exists(Config["json_web_path"]):  # pragma: no cover
            pathlib.Path(Config["json_web_path"]).mkdir(parents=True, exist_ok=True)

        now = datetime.now()
        new_json_file = os.path.join(
            Config["json_web_path"],
            "%s_%s.json_%s" % (cloud.name, filename, now.strftime("%Y-%m-%d_%H:%M:%S")),
        )
        json_file = os.path.join(Config["json_web_path"], "%s_%s.json" % (cloud.name, filename))
        with open(new_json_file, "w+") as _json_file:
            _json_file.seek(0)
            _json_file.write(content)
        os.chmod(new_json_file, 0o644)
        copyfile(new_json_file, json_file)


def main():
    tasks = []
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if Config["openstack_management"]:
        fn = functools.partial(make_env_json, "instackenv")
        tasks.append(fn)
    if Config["openshift_management"]:
        fn = functools.partial(make_env_json, "ocpinventory")
        tasks.append(fn)
    loop.run_until_complete(asyncio.gather(*[task() for task in tasks]))

    loop.close()


if __name__ == "__main__":  # pragma: no cover
    main()
