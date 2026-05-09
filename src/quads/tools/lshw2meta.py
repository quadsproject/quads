#!/usr/bin/env python3

import os
import json

from jsonpath_ng import parse
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from rich.table import Column, Table

from quads.config import Config
from quads.quads_api import QuadsApi

quads = QuadsApi(Config)

MD_DIR = "/opt/quads/lshw"
DISK_TYPES = {"nvme": "nvm", "sata": "ata", "scsi": "scsi"}


def b2g(num, metric=False):
    factor = 1024
    if metric:
        factor = 1000
    return round(num / (factor**3))


def main():
    json_files = [
        os.path.join(dirpath, f)
        for dirpath, _, files in os.walk(MD_DIR)
        for f in files
        if os.path.splitext(f)[1] == ".json" and os.path.getsize(os.path.join(dirpath, f))
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}", table_column=Column(min_width=30)),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Importing metadata", total=len(json_files))
        for filename in json_files:
            with open(filename) as _f:
                try:
                    data = json.load(_f)
                except json.JSONDecodeError:
                    progress.console.print(f"[red]Error decoding:[/] {filename}")
                    progress.advance(task)
                    continue
                children = parse("$..children[*]").find(data)
                hostname = parse("$.id").find(data)[0].value
                progress.update(task, description=f"[cyan]{hostname}[/]")
                host_obj = quads.get_host(hostname)
                if not host_obj:
                    progress.console.print(f"[yellow]Host not found:[/] {hostname}")
                    progress.advance(task)
                    continue

                rows = []  # (component, detail, action) tuples

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
                                quads.update_interface(hostname, host_interface.as_dict())
                                rows.append(("interface", f"{host_interface.name}  {host_interface.mac_address}", "updated"))
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
                                    d = {"disk_id": disk.id, "disk_type": disk_type, "size_gb": disk_size, "count": count}
                                    quads.update_disk(host_obj.name, d)
                                    rows.append(("disk", f"{disk_type}  {disk_size} GB  ×{count}", "updated"))
                                else:
                                    rows.append(("disk", f"{disk_type}  {disk_size} GB  ×{count}", "unchanged"))
                                break
                    else:
                        d = {"disk_type": disk_type, "size_gb": disk_size, "count": count}
                        quads.create_disk(host_obj.name, d)
                        rows.append(("disk", f"{disk_type}  {disk_size} GB  ×{count}", "created"))

                # memory
                for memory in host_obj.memory:
                    quads.remove_memory(str(memory.id))
                for child in [
                    child
                    for child in children
                    if child.value["class"] == "memory" and "bank" not in child.value["id"]
                ]:
                    if child.value.get("size") and child.value.get("handle") and "cache" not in child.value["id"]:
                        d = {"handle": child.value.get("handle"), "size_gb": b2g(int(child.value["size"]))}
                        quads.create_memory(hostname, d)
                        rows.append(("memory", f"{d['handle']}  {d['size_gb']} GB", "created"))

                # processor
                for processor in host_obj.processors:
                    quads.remove_processor(str(processor.id))
                # CPU
                for child in [child for child in children if child.value["class"] == "processor"]:
                    configuration = child.value.get("configuration")
                    if configuration.get("cores") and configuration.get("threads"):
                        d = {
                            "handle": child.value.get("handle"),
                            "vendor": child.value.get("vendor"),
                            "product": child.value.get("product"),
                            "cores": int(configuration.get("cores")),
                            "threads": int(configuration.get("threads")),
                            "processor_type": "CPU",
                        }
                        quads.create_processor(hostname, d)
                        rows.append(("cpu", f"{d['vendor']}  {d['product']}  {d['cores']}c/{d['threads']}t", "created"))
                # GPU
                recognized_gpu_drivers = {"nouveau"}
                recognized_gpu_controllers = {"3d controller", "display controller"}
                for child in [child for child in children if child.value["class"] == "display"]:
                    configuration = child.value.get("configuration")
                    description = child.value.get("description")
                    driver = configuration.get("driver")

                    driver_lower = driver.lower() if driver else ""
                    description_lower = description.lower() if description else ""

                    driver_recognized = driver_lower in recognized_gpu_drivers
                    is_3d_controller = description_lower in recognized_gpu_controllers

                    if driver_recognized or is_3d_controller:
                        d = {
                            "handle": child.value.get("handle"),
                            "vendor": child.value.get("vendor"),
                            "product": child.value.get("product"),
                            "processor_type": "GPU",
                        }
                        quads.create_processor(hostname, d)
                        rows.append(("gpu", f"{d['vendor']}  {d['product']}", "created"))

                if progress.console.is_terminal:
                    table = Table(title=f"[bold]{hostname}[/]", show_header=True, header_style="bold cyan", min_width=60)
                    table.add_column("Component", style="cyan", min_width=10)
                    table.add_column("Detail", min_width=30)
                    table.add_column("Action", style="green", min_width=8)
                    for row in rows:
                        table.add_row(*row)
                    progress.console.print(table)
                else:
                    print(f"{hostname}:")
                    for component, detail, action in rows:
                        print(f"  {component:10}  {detail}  [{action}]")

                progress.advance(task)


if __name__ == "__main__":  # pragma: no cover
    main()
