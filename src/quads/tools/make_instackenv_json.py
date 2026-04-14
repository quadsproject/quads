#!/usr/bin/env python3

import asyncio
import functools
import json
import os
import time
import pathlib
from collections import defaultdict
from datetime import datetime
from shutil import copyfile

from quads.quads_api import QuadsApi
from quads.tools.external.foreman import Foreman
from quads.config import Config
from quads.tools.helpers import strtobool

quads = QuadsApi(Config)


def cleanup_old_json_files():
    """Clean up old timestamped JSON files based on retention policy."""
    if not os.path.exists(Config["json_web_path"]):
        return

    # Clean up old timestamped JSON files based on retention policy
    now = time.time()
    retention_seconds = Config["json_retention_days"] * 86400
    cutoff_time = now - retention_seconds

    try:
        all_files = os.listdir(Config["json_web_path"])
    except OSError as e:
        print(f"ERROR: Cannot list files in {Config['json_web_path']}: {e}")
        return

    # Match timestamped files: cloud*_*.json_YYYY-MM-DD_HH:MM:SS
    # The ":" in timestamp makes them easy to identify
    old_jsons = [f for f in all_files if ":" in f and f.endswith(tuple(f.split(":")[-1]))]

    deleted_count = 0
    error_count = 0

    for file in old_jsons:
        file_path = os.path.join(Config["json_web_path"], file)
        try:
            file_mtime = os.stat(file_path).st_mtime
            if file_mtime < cutoff_time:
                os.remove(file_path)
                deleted_count += 1
        except FileNotFoundError:
            # File was already deleted, possibly by another process
            pass
        except OSError as e:
            print(f"WARN: Cannot delete {file}: {e}")
            error_count += 1

    if deleted_count > 0:
        print(f"INFO: Cleaned up {deleted_count} old JSON file(s) (retention: {Config['json_retention_days']} days)")
    if error_count > 0:
        print(f"WARN: Failed to delete {error_count} file(s) due to errors")


async def make_env_json(filename):
    """Generate instackenv or ocpinventory JSON files for all clouds."""
    start_time = time.time()

    # Initialize Foreman client if needed
    foreman = None
    if not Config["foreman_unavailable"]:
        foreman = Foreman(
            Config["foreman_api_url"],
            Config["foreman_username"],
            Config["foreman_password"],
        )

    # Ensure output directory exists once
    if not os.path.exists(Config["json_web_path"]):  # pragma: no cover
        os.makedirs(Config["json_web_path"])

    # Fetch all data upfront to minimize API calls
    print(f"INFO: Fetching clouds and hosts for {filename}...")
    cloud_list = quads.get_clouds()
    all_hosts = quads.get_hosts()

    # Build a mapping of cloud_name -> list of hosts for faster lookups
    hosts_by_cloud = defaultdict(list)
    for host in all_hosts:
        hosts_by_cloud[host.cloud.name].append(host)

    # Pre-fetch all active assignments to avoid per-cloud API calls
    try:
        all_assignments = quads.get_active_assignments()
        assignments_by_cloud = {ass.cloud.name: ass for ass in all_assignments}
    except Exception as e:
        print(f"WARN: Could not fetch assignments: {e}")
        assignments_by_cloud = {}

    clouds_processed = 0
    hosts_processed = 0

    for cloud in cloud_list:
        host_list = hosts_by_cloud.get(cloud.name, [])

        # Skip clouds with no hosts to save processing time
        if not host_list:
            continue

        assignment = assignments_by_cloud.get(cloud.name)
        foreman_password = Config["ipmi_password"]
        if assignment and assignment.ticket:
            foreman_password = f"{Config['infra_location']}@{assignment.ticket}"

        data = defaultdict(list)

        # Batch process hosts for this cloud
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
                hosts_processed += 1

        # Only write files if there's data
        if data["nodes"]:
            content = json.dumps(data, indent=4, sort_keys=True)

            now = datetime.now()
            new_json_file = os.path.join(
                Config["json_web_path"],
                "%s_%s.json_%s" % (cloud.name, filename, now.strftime("%Y-%m-%d_%H:%M:%S")),
            )
            json_file = os.path.join(Config["json_web_path"], "%s_%s.json" % (cloud.name, filename))

            try:
                with open(new_json_file, "w") as _json_file:
                    _json_file.write(content)
                os.chmod(new_json_file, 0o644)
                copyfile(new_json_file, json_file)
                clouds_processed += 1
            except OSError as e:
                print(f"ERROR: Failed to write {new_json_file}: {e}")

    elapsed = time.time() - start_time
    print(f"INFO: Processed {clouds_processed} clouds, {hosts_processed} hosts for {filename} in {elapsed:.2f}s")


def main():
    # Clean up old JSON files once before generating new ones
    cleanup_old_json_files()

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
