#!/usr/bin/env python3

import os
import json

from jsonpath_ng import parse

from quads.config import Config
from quads.quads_api import QuadsApi

quads = QuadsApi(Config)

MD_DIR = "/opt/quads/lshw"
DISK_TYPES = {"nvme": "nvm", "sata": "ata", "scsi": "scsi"}


def b2g(num, metric=False):  # pragma: no cover
    factor = 1024
    if metric:
        factor = 1000
    return round(num / (factor**3))


for _d, _, _files in os.walk(MD_DIR):  # pragma: no cover
    for _file in _files:
        filename = os.path.join(MD_DIR, _file)
        if os.path.getsize(filename):
            path, extension = os.path.splitext(filename)
            if extension == ".json":
                with open(filename) as _f:
                    try:
                        data = json.load(_f)
                    except json.JSONDecodeError:
                        print(f"Error decoding: {filename}")
                        continue
                    children = parse("$..children[*]").find(data)
                    hostname = parse("$.id").find(data)[0].value
                    print(f"Processing: {hostname}")
                    host_obj = quads.get_host(hostname)
                    if not host_obj:
                        print(f"Host not found: {hostname}")
                        break
                    # interfaces
                    for child in [child for child in children if child.value["class"] == "network"]:
                        if child.value.get("vendor"):
                            for host_interface in host_obj.interfaces:
                                if host_interface.mac_address == child.value["serial"]:
                                    host_interface.vendor = child.value.get("vendor")
                                    host_interface.logical_name = child.value.get("logicalname")
                                    speed = child.value["configuration"].get("speed")
                                    if speed:
                                        speed = int("".join(filter(str.isdigit, speed)))
                                    host_interface.speed = speed
                                    interface = quads.update_interface(hostname, host_interface.as_dict())
                                    print(f"  Updated interface: {host_interface.as_dict()}")
                    # disks
                    disk_nodes = [node.context.value for node in parse("$..class").find(data) if node.value == "disk"]
                    disks = {}
                    for child in disk_nodes:
                        if child.get("size"):
                            disk_type = None
                            for dt, sub in DISK_TYPES.items():
                                if child.get("description").lower().startswith(sub):
                                    disk_type = dt
                                    break
                            disk_size = b2g(int(child.get("size")), True)
                            disks[f"{disk_type}|{str(disk_size)}"] = disks.get(f"{disk_type}|{str(disk_size)}", 0) + 1

                    for key, count in disks.items():
                        disk_type, disk_size = key.split("|")
                        filters = {
                            "name": host_obj.name,
                            "disks.disk_type": disk_type,
                            "disks.size_gb": disk_size,
                        }
                        host = quads.filter_hosts(filters)
                        if host:
                            for disk in host[0].disks:
                                if disk.disk_type == disk_type and disk.size_gb == int(disk_size):
                                    if disk.count != count:
                                        data = {
                                            "disk_id": disk.id,
                                            "disk_type": disk_type,
                                            "size_gb": disk_size,
                                            "count": count,
                                        }
                                        quads.update_disk(host_obj.name, data)
                                        print(f"  Updated disk: {data}")
                                    else:
                                        print(f"  Disk already exists: {disk_type, disk_size, count}")
                                    break
                        else:
                            data = {
                                "disk_type": disk_type,
                                "size_gb": disk_size,
                                "count": count,
                            }
                            disk = quads.create_disk(host_obj.name, data)
                            print(f"  Created disk: {data}")

                    # memory
                    for memory in host_obj.memory:
                        quads.remove_memory(str(memory.id))
                    for child in [
                        child
                        for child in children
                        if child.value["class"] == "memory" and "bank" not in child.value["id"]
                    ]:
                        if child.value.get("size") and child.value.get("handle") and "cache" not in child.value["id"]:
                            data = {
                                "handle": child.value.get("handle"),
                                "size_gb": b2g(int(child.value["size"])),
                            }
                            quads.create_memory(
                                hostname,
                                data,
                            )
                            print(f"  Created memory: {data}")

                    # processor
                    for processor in host_obj.processors:
                        quads.remove_processor(str(processor.id))
                    # CPU
                    for child in [child for child in children if child.value["class"] == "processor"]:
                        configuration = child.value.get("configuration")
                        if configuration.get("cores") and configuration.get("threads"):
                            data = {
                                "handle": child.value.get("handle"),
                                "vendor": child.value.get("vendor"),
                                "product": child.value.get("product"),
                                "cores": int(configuration.get("cores")),
                                "threads": int(configuration.get("threads")),
                                "processor_type": "CPU",
                            }
                            processor = quads.create_processor(
                                hostname,
                                data,
                            )
                            print(f"  Created CPU processor: {data}")
                    # GPU
                    for child in [child for child in children if child.value["class"] == "display"]:
                        configuration = child.value.get("configuration")
                        if configuration.get("driver") == "nouveau":
                            data = {
                                "handle": child.value.get("handle"),
                                "vendor": child.value.get("vendor"),
                                "product": child.value.get("product"),
                                "processor_type": "GPU",
                            }
                            processor = quads.create_processor(
                                hostname,
                                data,
                            )
                            print(f"  Created GPU processor: {data}")
