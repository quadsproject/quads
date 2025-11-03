import re

from datetime import datetime, time

from flask import Blueprint, flash, redirect, url_for, render_template, request, jsonify

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
foreman = Foreman(
    Config["foreman_api_url"],
    Config["foreman_username"],
    Config["foreman_password"],
)
cloud_operation = CloudOperations(quads_api=quads, foreman=foreman)


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
    clouds_summary = await cloud_operation.get_cloud_summary_report()
    return jsonify(clouds_summary)


@wiki_bp.route("/utilization")
async def utilization():
    daily_utilization = await cloud_operation.get_daily_utilization()
    return jsonify(daily_utilization)


@wiki_bp.route("/managed/<cloud>")
async def managed(cloud):
    managed_nodes = await cloud_operation.get_managed_nodes(cloud)
    return jsonify(managed_nodes)


@wiki_bp.route("/unmanaged")
async def unmanaged():
    unmanaged_hosts = await cloud_operation.get_unmanaged_hosts(exclude_hosts=Config["exclude_hosts"])
    return jsonify(unmanaged_hosts)


@wiki_bp.route("/broken")
async def broken():
    domain_broken_hosts = await cloud_operation.get_domain_broken_hosts(domain=Config["domain"])
    return jsonify(domain_broken_hosts)


@wiki_bp.route("/available", methods=["GET", "POST"])
async def available():
    show_gpu = Config.get("show_gpu")
    search = ModelSearchForm(request.form)
    if request.method == "POST":
        return await search_results(search)

    return render_template("wiki/available.html", form=search, available_hosts=[], show_gpu=show_gpu)


@wiki_bp.route("/results")
async def search_results(search):
    show_gpu = Config.get("show_gpu")
    available_hosts_list = await available_hosts(search)
    return render_template("wiki/available.html", form=search, available_hosts=available_hosts_list, show_gpu=show_gpu)


@wiki_bp.route("/available_hosts")
async def available_hosts(search):
    models = search.data["model"]
    disk_types = search.data["disk_types"]
    has_gpu = search.data["has_gpu"]
    disk_size_operator = search.data["disk_size_operator"]
    disk_size_value = search.data["disk_size_value"]
    disk_count_operator = search.data["disk_count_operator"]
    disk_count_value = search.data["disk_count_value"]
    nic_vendors = search.data["nic_vendors"]
    nic_speed_operator = search.data["nic_speed_operator"]
    nic_speed_value = search.data["nic_speed_value"]
    try:
        start, end = [datetime.strptime(date, "%Y-%m-%d").date() for date in search.data["date_range"].split(" - ")]
        start = datetime.combine(start, time(hour=22)).strftime("%Y-%m-%dT%H:%M")
        end = datetime.combine(end, time(hour=22)).strftime("%Y-%m-%dT%H:%M")
    except ValueError:
        return jsonify([])

    try:
        data = {"start": start, "end": end}
        if models:
            models = [model.upper() for model in models]
            data["model__in"] = ",".join(models)

        if disk_types:
            data["disks.disk_type__in"] = ",".join(disk_types)

        if has_gpu:
            data["processors.processor_type"] = "GPU"

        if disk_size_operator and disk_size_value:
            key = f"disks.size_gb__{disk_size_operator}"
            if disk_size_operator == "eq":
                key = "disks.size_gb"
            data[key] = disk_size_value

        if disk_count_operator and disk_count_value:
            key = f"disks.count__{disk_count_operator}"
            if disk_count_operator == "eq":
                key = "disks.count"
            data[key] = disk_count_value

        if nic_vendors:
            data["interfaces.vendor__in"] = ",".join(nic_vendors)

        if nic_speed_operator and nic_speed_value:
            key = f"interfaces.speed__{nic_speed_operator}"
            if nic_speed_operator == "eq":
                key = "interfaces.speed"
            data[key] = nic_speed_value

        hosts = quads.filter_available(data=data)
        available_hosts = []
        currently_scheduled = [schedule.host_id for schedule in quads.get_current_schedules()]
        for host in hosts:
            host_dict = host.as_dict()
            host_dict["current"] = host.id in currently_scheduled
            available_hosts.append(host_dict)
        return jsonify(available_hosts)
    except Exception as ex:
        return jsonify({"error": str(ex)})


@wiki_bp.route("/dashboard")
async def create_inventory():
    headers = [
        "U",
        "ServerHostnamePublic",
        "MAC",
        "IP",
        "IPMIADDR",
        "IPMIURL",
        "IPMIMAC",
        "Workload",
        "Owner",
    ]
    try:
        racks = quads.get_host_racks()
        if not racks:
            flash("No racks found in the database.", "error")
            return redirect(url_for("wiki.index"))
    except (APIBadRequest, APIServerException):
        flash("Failed to retrieve racks from the database.", "error")
        return redirect(url_for("wiki.index"))
    return render_template("wiki/inventory.html", headers=headers, racks=" ".join(racks.keys()))


@wiki_bp.route("/rack/<rack>")
async def rack(rack):
    hosts = quads.filter_hosts(data={"rack": rack})
    blacklist = re.compile("|".join([re.escape(word) for word in Config["exclude_hosts"].split("|")]))
    host_details = []
    assignments_cache = {}
    error_occurred = False

    for host in hosts:
        foreman_host = {}
        response = await foreman.get_host(host.name)
        if not response:
            error_occurred = True
        foreman_host = response.get(host.name, foreman_host)
        if not blacklist.search(host.name):
            if host and not host.retired:
                if assignments_cache.get(host.cloud.name, False):
                    assignment = assignments_cache[host.cloud.name]
                else:
                    assignment = quads.get_active_cloud_assignment(host.cloud.name)
                    assignments_cache[host.cloud.name] = assignment
                owner = assignment.owner if assignment else "QUADS"
                host_details.append(
                    {
                        "U": host.uloc,
                        "ServerHostnamePublic": host.name.split(".")[0],
                        "MAC": foreman_host.get("mac", ""),
                        "IP": foreman_host.get("ip", ""),
                        "IPMIADDR": foreman_host.get("sp_ip", ""),
                        "IPMIURL": host.name,
                        "IPMIMAC": foreman_host.get("sp_mac", ""),
                        "Workload": host.cloud.name,
                        "Owner": owner,
                    }
                )

    return jsonify({"host_details": host_details, "error": error_occurred})


@wiki_bp.route("/host/<hostname>")
async def host_details(hostname):
    host_details = quads.get_host(hostname)

    return render_template("wiki/host.html", host=host_details)


@wiki_bp.route("/vlans")
async def create_vlans():
    vlans = await cloud_operation.get_vlans_list()
    return render_template("wiki/vlans.html", vlans=vlans)
