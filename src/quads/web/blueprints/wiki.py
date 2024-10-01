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
def index():
    return redirect(url_for("assignments"))


@wiki_bp.route("/assignments", methods=["GET", "POST"])
def assignments():
    headers = ["NAME", "SUMMARY", "OWNER", "REQUEST", "STATUS", "OSPENV", "OCPINV"]
    host_headers = [
        "ServerHostnamePublic",
        "OutOfBand",
        "DateStartAssignment",
        "DateEndAssignment",
        "TotalDuration",
        "TimeRemaining",
    ]
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    clouds_summary = cloud_operation.get_cloud_summary_report()
    daily_utilization = cloud_operation.get_daily_utilization()
    managed_nodes = cloud_operation.get_managed_nodes()
    domain_broken_hosts = cloud_operation.get_domain_broken_hosts(domain=Config["domain"])
    unmanaged_hosts = cloud_operation.get_unmanaged_hosts(exclude_hosts=Config["exclude_hosts"])
    return render_template(
        "wiki/assignments.html",
        headers=headers,
        clouds_summary=clouds_summary,
        ticket_url=Config.get("ticket_url"),
        ticket_queue=Config.get("ticket_queue"),
        quads_url=Config.get("quads_url"),
        openshift_management=Config["openshift_management"],
        daily_utilization=daily_utilization,
        domain_broken_hosts=domain_broken_hosts,
        host_headers=host_headers,
        managed_nodes=managed_nodes,
        unmanaged_hosts=unmanaged_hosts,
    )


@wiki_bp.route("/available", methods=["GET", "POST"])
def available():
    search = ModelSearchForm(request.form)
    if request.method == "POST":
        return search_results(search)

    return render_template("wiki/available.html", form=search, available_hosts=[])


@wiki_bp.route("/results")
def search_results(search):
    available_hosts_list = available_hosts(search)
    return render_template("wiki/available.html", form=search, available_hosts=available_hosts_list)


@wiki_bp.route("/available_hosts")
def available_hosts(search):
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
def create_inventory():
    all_hosts = loop.run_until_complete(foreman.get_all_hosts())
    blacklist = re.compile("|".join([re.escape(word) for word in Config["exclude_hosts"].split("|")]))
    hosts = {}
    for host, properties in all_hosts.items():
        if not blacklist.search(host):
            if properties.get("sp_name", False):
                properties["host_ip"] = properties["ip"]
                properties["host_mac"] = properties["mac"]
                properties["ip"] = properties.get("sp_ip")
                properties["mac"] = properties.get("sp_mac")
                svctag = ""
                properties["svctag"] = svctag.strip()
                hosts[host] = properties
    all_hosts = {}
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
    for rack in Config["racks"].split():
        for host, properties in hosts.items():
            if rack in host:
                host_obj = quads.get_host(host)
                if host_obj and not host_obj.retired:
                    assignment = quads.get_active_cloud_assignment(host_obj.cloud.name)
                    owner = assignment.owner if assignment else "QUADS"
                    all_hosts.setdefault(rack, []).append(
                        {
                            "U": host_obj.name.split("-")[1][1:],
                            "ServerHostnamePublic": host_obj.name.split(".")[0],
                            "Serial": properties.get("svctag", ""),
                            "MAC": properties.get("host_mac", ""),
                            "IP": properties.get("host_ip", ""),
                            "IPMIADDR": properties.get("ip", ""),
                            "IPMIURL": host_obj.name,
                            "IPMIMAC": properties.get("mac", ""),
                            "Workload": host_obj.cloud.name,
                            "Owner": owner,
                        }
                    )
    return render_template("wiki/inventory.html", headers=headers, all_hosts=all_hosts)


@wiki_bp.route("/vlans")
def create_vlans():
    cloud_operation = CloudOperations(quads_api=quads, foreman=foreman, loop=loop)
    vlans = cloud_operation.get_vlans_list()
    return render_template("wiki/vlans.html", vlans=vlans)
