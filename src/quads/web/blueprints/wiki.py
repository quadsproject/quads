import asyncio
import re

from datetime import datetime, time

from flask import Blueprint, redirect, url_for, render_template, request, jsonify

from quads.web.blueprints.common import WEB_CONTENT_PATH
from quads.web.forms import ModelSearchForm
from quads.quads_api import QuadsApi, APIBadRequest, APIServerException
from quads.tools.external.foreman import Foreman
from quads.config import Config
from quads.web.controller.CloudOperations import CloudOperations

wiki_bp = Blueprint(
    "wiki",
    __name__,
    template_folder=WEB_CONTENT_PATH,
)

quads = QuadsApi(Config)
loop = asyncio.new_event_loop()
foreman = Foreman(
    Config["foreman_api_url"],
    Config["foreman_username"],
    Config["foreman_password"],
    loop=loop,
)


@wiki_bp.route("/", methods=["GET", "POST"])
async def index():
    return redirect(url_for("wiki.assignments"))


@wiki_bp.route("/assignments", methods=["GET", "POST"])
async def assignments():
    headers = ["NAME", "SUMMARY", "OWNER", "REQUEST", "STATUS", "OSPENV", "OCPINV"]
    host_headers = [
        "ServerHostnamePublic",
        "OutOfBand",
        "DateStartAssignment",
        "DateEndAssignment",
        "TotalDuration",
        "TimeRemaining",
    ]
    return render_template(
        "wiki/assignments.html",
        headers=headers,
        ticket_url=Config.get("ticket_url"),
        ticket_queue=Config.get("ticket_queue"),
        quads_url=Config.get("quads_url"),
        openshift_management=Config["openshift_management"],
        host_headers=host_headers,
    )


@wiki_bp.route("/summary")
async def summary():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    clouds_summary = await cloud_operation.get_cloud_summary_report()
    return jsonify(clouds_summary)


@wiki_bp.route("/utilization")
async def utilization():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    daily_utilization = await cloud_operation.get_daily_utilization()
    return jsonify(daily_utilization)


@wiki_bp.route("/managed/<cloud>")
async def managed(cloud):
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    managed_nodes = await cloud_operation.get_managed_nodes(cloud)
    return jsonify(managed_nodes)


@wiki_bp.route("/unmanaged")
async def unmanaged():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    unmanaged_hosts = await cloud_operation.get_unmanaged_hosts(exclude_hosts=Config["exclude_hosts"])
    return jsonify(unmanaged_hosts)


@wiki_bp.route("/broken")
async def broken():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    domain_broken_hosts = await cloud_operation.get_domain_broken_hosts(domain=Config["domain"])
    return jsonify(domain_broken_hosts)


@wiki_bp.route("/available", methods=["GET", "POST"])
async def available():
    search = ModelSearchForm(request.form)
    if request.method == "POST":
        return await search_results(search)

    return render_template("wiki/available.html", form=search, available_hosts=[])


@wiki_bp.route("/results")
async def search_results(search):
    available_hosts_list = await available_hosts(search)
    return render_template("wiki/available.html", form=search, available_hosts=available_hosts_list)


@wiki_bp.route("/available_hosts")
async def available_hosts(search):
    models = search.data["model"]
    try:
        start, end = [datetime.strptime(date, "%Y-%m-%d").date() for date in search.data["date_range"].split(" - ")]
        start = datetime.combine(start, time(hour=22)).strftime("%Y-%m-%dT%H:%M")
        end = datetime.combine(end, time(hour=22)).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return jsonify([])

    try:
        hosts = quads.filter_available(data={"start": start, "end": end})
        if models:
            models = [model.upper() for model in models]
            hosts = [host for host in hosts if host.model in models]

        available_hosts = []
        currently_scheduled = [schedule.host_id for schedule in quads.get_current_schedules()]
        for host in hosts:
            current = True if host.id in currently_scheduled else False
            host_dict = {
                "name": host.name,
                "cloud": host.cloud.name,
                "model": host.model,
                "current": current,
                "disks": [
                    {
                        "disk_type": disk.disk_type,
                        "disk_size": disk.size_gb,
                        "disk_count": disk.count,
                    }
                    for disk in host.disks
                ],
            }
            available_hosts.append(host_dict)
    except (APIBadRequest, APIServerException):
        return jsonify({})

    return jsonify(available_hosts)


@wiki_bp.route("/dashboard")
async def create_inventory():
    headers = [
        "U",
        "ServerHostnamePublic",
        "Serial",
        "MAC",
        "IP",
        "IPMIADDR",
        "IPMIURL",
        "IPMIMAC",
        "Workload",
        "Owner",
    ]
    return render_template("wiki/inventory.html", headers=headers, racks=Config["racks"])


@wiki_bp.route("/rack/<rack>")
async def rack(rack):
    rack_hosts = await foreman.get_hosts_by_rack(rack)
    blacklist = re.compile("|".join([re.escape(word) for word in Config["exclude_hosts"].split("|")]))
    host_details = []
    assignments_cache = {}
    for host, properties in rack_hosts.items():
        if not blacklist.search(host) and properties.get("sp_name", False):
            try:
                host_obj = quads.get_host(host)
            except (APIBadRequest, APIServerException):
                continue
            if host_obj and not host_obj.retired:
                if assignments_cache.get(host_obj.cloud.name, False):
                    assignment = assignments_cache[host_obj.cloud.name]
                else:
                    assignment = quads.get_active_cloud_assignment(host_obj.cloud.name)
                    assignments_cache[host_obj.cloud.name] = assignment
                owner = assignment.owner if assignment else "QUADS"
                host_details.append(
                    {
                        "U": host_obj.name.split("-")[1][1:],
                        "ServerHostnamePublic": host_obj.name.split(".")[0],
                        "Serial": properties.get("svctag", ""),
                        "MAC": properties.get("mac", ""),
                        "IP": properties.get("ip", ""),
                        "IPMIADDR": properties.get("sp_ip", ""),
                        "IPMIURL": host_obj.name,
                        "IPMIMAC": properties.get("sp_mac", ""),
                        "Workload": host_obj.cloud.name,
                        "Owner": owner,
                    }
                )
    return jsonify(host_details)


@wiki_bp.route("/vlans")
async def create_vlans():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    vlans = await cloud_operation.get_vlans_list()
    return render_template("wiki/vlans.html", vlans=vlans)
