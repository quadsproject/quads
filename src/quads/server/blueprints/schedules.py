from datetime import datetime, timedelta
from calendar import day_name

from flask import Blueprint, Response, g, jsonify, make_response, request

from quads.config import Config
from quads.server.blueprints import check_access
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import BaseDao, EntryNotFound, InvalidArgument, SQLError
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.notification import NotificationDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.models import Schedule, db

schedule_bp = Blueprint("schedules", __name__)


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
        _start = datetime.strptime(start, "%Y-%m-%d %H:%M") if isinstance(start, str) else start
        _end = datetime.strptime(end, "%Y-%m-%d %H:%M") if isinstance(end, str) else end
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
