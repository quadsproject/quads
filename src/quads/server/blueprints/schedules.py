import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from calendar import day_name
from jinja2 import Template

from flask import Blueprint, Response, current_app, g, jsonify, make_response, request

from quads.config import Config
from quads.server.blueprints import check_access
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import BaseDao, EntryNotFound, InvalidArgument, SQLError
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.notification import NotificationDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.models import db
from quads.server.dao.vlan import VlanDao

logger = logging.getLogger(__name__)

schedule_bp = Blueprint("schedules", __name__)


def _parse_datetime_with_now(date_str):
    if isinstance(date_str, str) and date_str.lower() == "now":
        return datetime.now()
    if isinstance(date_str, str):
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    return date_str


def _trigger_jira_notification(assignment, hostnames, start, end):
    ticketing_dispatcher = current_app.extensions.get("plugin_dispatchers", {}).get("ticketing")
    if not ticketing_dispatcher:
        logger.warning("Ticketing system not configured, skipping notification")
        return False

    conf = Config
    template_file = "jira_ticket_assignment"
    template_path = os.path.join(conf.TEMPLATES_PATH, template_file)

    try:
        with open(template_path) as f:
            template = Template(f.read())
    except IOError:
        logger.error("Failed to load template: %s", template_path)
        return False

    jira_docs_links = conf.get("jira_docs_links", "").split(",")
    jira_vlans_docs_links = conf.get("jira_vlans_docs_links", "").split(",")

    host_list_str = "\n".join(hostnames)

    comment = template.render(
        schedule_start=start,
        schedule_end=end,
        cloud=assignment.cloud.name,
        jira_docs_links=jira_docs_links,
        jira_vlans_docs_links=jira_vlans_docs_links,
        host_list=host_list_str,
        vlan=assignment.vlan,
    )

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            ticketing_dispatcher.post_comment(assignment.ticket, comment)
        )
        if not result:
            logger.error("Failed to post comment for ticket %s", assignment.ticket)
            return False

        transitions = loop.run_until_complete(
            ticketing_dispatcher.get_transitions(assignment.ticket)
        )
        for transition in transitions:
            t_name = transition.get("name")
            if t_name and t_name.lower() == "scheduled":
                transition_id = transition.get("id")
                loop.run_until_complete(
                    ticketing_dispatcher.post_transition(assignment.ticket, transition_id)
                )
                logger.info("Ticket %s transitioned to 'scheduled'", assignment.ticket)
                break

        return True
    except Exception as ex:
        logger.error("Ticketing notification failed for ticket %s: %s", assignment.ticket, ex)
        return False
    finally:
        loop.close()


@schedule_bp.route("/")
def get_schedules() -> Response:
    if request.args:
        try:
            _schedules = ScheduleDao.filter_schedule_dict(request.args)
        except (EntryNotFound, InvalidArgument) as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    else:
        _schedules = ScheduleDao.get_schedules()
    return jsonify([_schedule.as_dict() for _schedule in _schedules])


@schedule_bp.route("/<schedule_id>")
def get_schedule(schedule_id: int) -> Response:
    _schedule = ScheduleDao.get_schedule(int(schedule_id))
    if not _schedule:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Schedule not found: {schedule_id}",
        }
        return make_response(jsonify(response), 400)
    return jsonify(_schedule.as_dict())


@schedule_bp.route("/current")
def get_current_schedule() -> Response:
    data = request.args.to_dict()
    date = data.get("date")
    hostname = data.get("host")
    cloud_name = data.get("cloud")
    _kwargs = {}
    if date:
        _kwargs["date"] = datetime.strptime(date, "%Y-%m-%dT%H:%M")
    if hostname:
        host = HostDao.get_host(hostname)
        _kwargs["host"] = host
    if cloud_name:
        cloud = CloudDao.get_cloud(cloud_name)
        _kwargs["cloud"] = cloud
    _schedules = ScheduleDao.get_current_schedule(**_kwargs)
    return jsonify([_schedule.as_dict() for _schedule in _schedules])


@schedule_bp.route("/future")
def get_future_schedule() -> Response:
    data = request.args.to_dict()
    hostname = data.get("host")
    cloud_name = data.get("cloud")
    host = HostDao.get_host(hostname)
    cloud = CloudDao.get_cloud(cloud_name)
    _schedules = ScheduleDao.get_future_schedules(host, cloud)
    return jsonify([_schedule.as_dict() for _schedule in _schedules])


@schedule_bp.route("/hosts_range")
def get_hosts_range_schedule() -> Response:
    data = request.args.to_dict()
    start = data.get("start")
    end = data.get("end")
    _schedules = ScheduleDao.get_hosts_range_schedules(start, end)
    return jsonify({row[0]: row[1] for row in _schedules})


@schedule_bp.route("/", methods=["POST"])
@check_access(["admin", "user"])
def create_schedule() -> Response:
    data = request.get_json()
    hostname = data.get("hostname")
    cloud = data.get("cloud")
    if not cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: cloud",
        }
        return make_response(jsonify(response), 400)

    _cloud = CloudDao.get_cloud(cloud)
    if not _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud not found: {cloud}",
        }
        return make_response(jsonify(response), 400)

    _assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
    if not _assignment:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"No active assignment for cloud: {cloud}",
        }
        return make_response(jsonify(response), 400)
    if not _assignment.is_self_schedule and "admin" not in [role.name for role in g.current_user.roles]:
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": f"You({g.current_user.email}) don't have permission to create a schedule on {cloud}",
        }
        return make_response(jsonify(response), 403)

    existing_schedules = ScheduleDao.get_current_schedule(cloud=_cloud)
    if _assignment.is_self_schedule and len(existing_schedules) >= Config.get("ssm_host_limit", 10):
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud {cloud} has reached the maximum number of hosts",
        }
        return make_response(jsonify(response), 400)

    if not hostname:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: hostname",
        }
        return make_response(jsonify(response), 400)

    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)

    if _assignment.is_self_schedule:
        if not _host.can_self_schedule:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Host {hostname} is not allowed to self-schedule",
            }
            return make_response(jsonify(response), 400)

        start = datetime.now()

        ssm_deadline_day = Config.get("ssm_deadline_day", "sunday").lower()
        ssm_deadline_hour = Config.get("ssm_deadline_hour", "21")
        ssm_default_lifetime = Config.get("ssm_default_lifetime", 1)

        day_mapping = {day.lower(): i for i, day in enumerate(day_name)}
        target_day = day_mapping.get(ssm_deadline_day)
        current_day = start.weekday()

        days_ahead = target_day - current_day
        if days_ahead < ssm_default_lifetime:
            end = start.replace(hour=ssm_deadline_hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
        else:
            end = start + timedelta(days=ssm_default_lifetime)
    else:
        start = data.get("start")
        end = data.get("end")

    if not start or not end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: start or end",
        }
        return make_response(jsonify(response), 400)

    try:
        _start = _parse_datetime_with_now(start)
        _end = _parse_datetime_with_now(end)
    except ValueError:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DD HH:MM'",
        }
        return make_response(jsonify(response), 400)

    if _start > _end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range for start or end, start must be before end",
        }
        return make_response(jsonify(response), 400)

    if not ScheduleDao.is_host_available(hostname, _start, _end):
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Host is not available for the specified date range",
        }
        return make_response(jsonify(response), 400)

    try:
        _schedule_obj = ScheduleDao.create_schedule(start=_start, end=_end, assignment=_assignment, host=_host)
    except SQLError as ex:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(ex),
        }
        return make_response(jsonify(response), 400)

    if _assignment.notification.pre:
        try:
            NotificationDao.update_notification(_assignment.notification.id, pre=False)
        except SQLError as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    return jsonify(_schedule_obj.as_dict())


@schedule_bp.route("/<schedule_id>", methods=["PATCH"])
@check_access(["admin"])
def update_schedule(schedule_id: int) -> Response:
    data = request.get_json()
    hostname = data.get("hostname")
    cloud = data.get("cloud")

    schedule = ScheduleDao.get_schedule(int(schedule_id))
    if not schedule:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Schedule not found: {schedule_id}",
        }
        return make_response(jsonify(response), 400)

    if cloud:
        _cloud = CloudDao.get_cloud(cloud)
        if not _cloud:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Cloud not found: {cloud}",
            }
            return make_response(jsonify(response), 400)

    if hostname:
        _host = HostDao.get_host(hostname)
        if not _host:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Host not found: {hostname}",
            }
            return make_response(jsonify(response), 400)

    start = data.get("start")
    end = data.get("end")
    build_start = data.get("build_start")
    build_end = data.get("build_end")
    parsed_data = {}
    _format = "%Y-%m-%dT%H:%M"
    try:
        if start:
            _start = datetime.strptime(start, _format)
            parsed_data["start"] = _start
        if end:
            _end = datetime.strptime(end, _format)
            parsed_data["end"] = _end
        if build_start:
            _build_start = datetime.strptime(build_start, _format)
            parsed_data["build_start"] = _build_start
        if build_end:
            _build_end = datetime.strptime(build_end, _format)
            parsed_data["build_end"] = _build_end
    except ValueError:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'",
        }
        return make_response(jsonify(response), 400)

    if not start and not end and not build_start and not build_end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: start, end, build_start or build_end (specify at least one)",
        }
        return make_response(jsonify(response), 400)

    if start and end and _start > _end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range for start or end, start must be before end",
        }
        return make_response(jsonify(response), 400)

    if build_start and build_end and _build_start > _build_end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range for build_start or build_end, build_start must be before build_end",
        }
        return make_response(jsonify(response), 400)

    if start and build_start and _start > _build_start:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range for start or build_start, start must be before build_start",
        }
        return make_response(jsonify(response), 400)

    if end and build_end and _end < _build_end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range for end or build_end, build_end must be before end",
        }
        return make_response(jsonify(response), 400)

    updated_schedule = ScheduleDao.update_schedule(int(schedule_id), **parsed_data)

    _assignment = AssignmentDao.get_assignment(schedule.assignment.id)
    if _assignment.notification.pre:
        try:
            NotificationDao.update_notification(_assignment.notification.id, pre=False)
        except SQLError as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    return jsonify(updated_schedule.as_dict())


@schedule_bp.route("/<schedule_id>", methods=["DELETE"])
@check_access(["admin"])
def delete_schedule(schedule_id: int) -> Response:
    _schedule = ScheduleDao.get_schedule(schedule_id)
    if not _schedule:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Schedule not found: {schedule_id}",
        }
        return make_response(jsonify(response), 400)

    db.session.delete(_schedule)
    BaseDao.safe_commit()
    response = {
        "status_code": 200,
        "message": "Schedule deleted",
    }
    return jsonify(response)


@schedule_bp.route("/batch", methods=["POST"])
@check_access(["admin"])
def create_schedules_batch() -> Response:
    data = request.get_json()

    cloud_name = data.get("cloud")
    hostnames = data.get("hostnames")
    start = data.get("start")
    end = data.get("end")

    if not cloud_name:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: cloud",
        }
        return make_response(jsonify(response), 400)

    if not hostnames or not isinstance(hostnames, list):
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing or invalid argument: hostnames (must be a list)",
        }
        return make_response(jsonify(response), 400)

    if not start or not end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: start or end",
        }
        return make_response(jsonify(response), 400)

    _cloud = CloudDao.get_cloud(cloud_name)
    if not _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud not found: {cloud_name}",
        }
        return make_response(jsonify(response), 400)

    try:
        _start = _parse_datetime_with_now(start)
        _end = _parse_datetime_with_now(end)
    except ValueError:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DD HH:MM'",
        }
        return make_response(jsonify(response), 400)

    if _start >= _end:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date range: start must be before end",
        }
        return make_response(jsonify(response), 400)

    description = data.get("description")
    owner = data.get("owner")
    ticket = data.get("ticket")

    should_create_assignment = bool(description or owner or ticket)

    if should_create_assignment:
        if not description or not owner or not ticket:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": "When creating assignment, description, owner, and ticket are all required",
            }
            return make_response(jsonify(response), 400)

        existing_assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
        if existing_assignment:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"There is already an active assignment for {cloud_name} (ID: {existing_assignment.id}, owner: {existing_assignment.owner}). Terminate it first or use existing assignment by omitting assignment parameters.",
            }
            return make_response(jsonify(response), 400)

        vlan_id = data.get("vlan")
        _vlan = None
        if vlan_id:
            _vlan = VlanDao.get_vlan(int(vlan_id))
            if not _vlan:
                response = {
                    "status_code": 400,
                    "error": "Bad Request",
                    "message": f"Vlan not found: {vlan_id}",
                }
                return make_response(jsonify(response), 400)
    else:
        existing_assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
        if not existing_assignment:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"No active assignment for cloud: {cloud_name}",
            }
            return make_response(jsonify(response), 400)

    unavailable_hosts = []
    for hostname in hostnames:
        _host = HostDao.get_host(hostname)
        if not _host:
            unavailable_hosts.append(f"{hostname}: Host not found")
            continue

        if not ScheduleDao.is_host_available(hostname, _start, _end):
            unavailable_hosts.append(f"{hostname}: Not available for specified date range")

    if unavailable_hosts:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Some hosts are unavailable",
            "unavailable_hosts": unavailable_hosts,
        }
        return make_response(jsonify(response), 400)

    _assignment = None
    created_new_assignment = False
    assignment_id = None

    if should_create_assignment:
        ccuser = data.get("ccuser")
        if ccuser and isinstance(ccuser, str):
            ccuser = re.split(r"[, ]+", ccuser)

        kwargs = {
            "description": description,
            "owner": owner,
            "ticket": ticket,
            "qinq": data.get("qinq", 0),
            "wipe": str(data.get("wipe", True)).lower() in ["true", "y", 1, "yes"],
            "ccuser": ccuser,
            "cloud": cloud_name,
        }
        if vlan_id:
            _vlan = VlanDao.get_vlan(int(vlan_id))
            kwargs["vlan_id"] = int(vlan_id)

        try:
            _assignment = AssignmentDao.create_assignment(**kwargs)
            assignment_id = _assignment.id
            created_new_assignment = True
        except SQLError as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Failed to create assignment: {ex}",
            }
            return make_response(jsonify(response), 400)
    else:
        _assignment = existing_assignment
        assignment_id = _assignment.id

    schedules_created = []
    failed_schedules = []

    for hostname in hostnames:
        _host = HostDao.get_host(hostname)
        try:
            _schedule_obj = ScheduleDao.create_schedule(start=_start, end=_end, assignment=_assignment, host=_host)
            schedules_created.append(hostname)
        except SQLError as ex:
            failed_schedules.append(f"{hostname}: {ex}")

    if failed_schedules:
        if created_new_assignment:
            try:
                _assignment.active = False
                BaseDao.safe_commit()
            except Exception:
                pass

        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Some schedules failed to create",
            "failed_schedules": failed_schedules,
        }
        return make_response(jsonify(response), 400)

    if _assignment.notification.pre:
        try:
            NotificationDao.update_notification(_assignment.notification.id, pre=False)
        except SQLError:
            pass

    jira_updated = _trigger_jira_notification(_assignment, hostnames, start, end)

    response_data = {
        "assignment_id": assignment_id,
        "schedules_created": len(schedules_created),
        "hostnames": schedules_created,
        "jira_updated": jira_updated,
    }

    return jsonify(response_data)
