import json
from datetime import datetime

from flask import Blueprint, Response, jsonify, make_response, request

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import EntryNotFound
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.models import Schedule

moves_bp = Blueprint("moves", __name__)


def _progress_to_dict(schedule):
    return {
        "id": schedule.id,
        "host": schedule.host.name,
        "host_id": schedule.host_id,
        "source_cloud": schedule.move_source_cloud or schedule.host.cloud.name,
        "target_cloud": schedule.assignment.cloud.name,
        "status": schedule.move_status or "pending",
        "message": schedule.move_message,
        "error_message": schedule.move_error,
        "started_at": schedule.build_start.isoformat() if schedule.build_start else None,
        "completed_at": schedule.build_end.isoformat() if schedule.build_end else None,
        "stage_timestamps": json.loads(schedule.move_stage_timestamps) if schedule.move_stage_timestamps else {},
    }


@moves_bp.route("/")
def get_moves() -> Response:
    """
    Returns a list of hosts that need to be moved from one cloud to another.
        The function takes in a date parameter, which is used to determine the current schedule for each host.
        If no date is provided, the current time will be used instead.
        Specify the date as url argument, for which we want to get the moves.

    :return: A list of dictionaries, each dictionary containing the following keys: host, new, current
    """
    _date = datetime.now()
    _params = request.args.to_dict()
    result = []
    if _params.get("date"):
        _date = datetime.strptime(_params.get("date"), "%Y-%m-%dT%H:%M")
    try:
        _hosts = HostDao.get_hosts()
        for host in _hosts:
            _current_schedule = ScheduleDao.get_current_schedule(host=host, date=_date)
            _host_current_cloud = host.cloud
            _new_cloud = _current_schedule[0].assignment.cloud if _current_schedule else host.default_cloud
            if _new_cloud == _host_current_cloud:
                continue
            result.append(
                {
                    "host": host.name,
                    "new": _new_cloud.name,
                    "current": _host_current_cloud.name,
                }
            )
    except (IndexError, AttributeError):
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": "Something went wrong, please try again.",
        }
        return make_response(jsonify(response), 500)
    return jsonify(result)


@moves_bp.route("/progress/")
def get_all_move_status() -> Response:
    cloud = request.args.get("cloud")
    status = request.args.get("status")
    moves = ScheduleDao.get_active_moves(cloud=cloud, status=status)
    return jsonify([_progress_to_dict(m) for m in moves])


@moves_bp.route("/progress/<hostname>")
def get_move_status(hostname: str) -> Response:
    schedule = ScheduleDao.get_active_move_by_hostname(hostname)
    if not schedule:
        return make_response(
            jsonify({"error": "Not Found", "message": f"No active move for {hostname}"}),
            404,
        )
    return jsonify(_progress_to_dict(schedule))


@moves_bp.route("/progress/batch", methods=["POST"])
@check_access(["admin"])
def start_move_batch() -> Response:
    data = request.get_json()
    hostnames = data.get("hostnames", [])
    if not hostnames:
        return make_response(
            jsonify({"error": "Bad Request", "message": "hostnames list is required"}),
            400,
        )
    result = ScheduleDao.start_move_batch(hostnames)
    return make_response(jsonify(result), 201)


@moves_bp.route("/progress/<int:schedule_id>", methods=["PATCH"])
@check_access(["admin"])
def update_move_status(schedule_id: int) -> Response:
    data = request.get_json()
    field_map = {"status": "move_status", "message": "move_message", "error_message": "move_error"}
    update_data = {field_map[k]: v for k, v in data.items() if k in field_map}
    valid_statuses = Schedule.VALID_STATUSES
    if "move_status" in update_data and update_data["move_status"] not in valid_statuses:
        return make_response(
            jsonify({"error": "Bad Request", "message": f"Invalid status: {update_data['move_status']}"}),
            400,
        )
    try:
        schedule = ScheduleDao.update_move_status(schedule_id, **update_data)
    except EntryNotFound:
        return make_response(
            jsonify({"error": "Not Found", "message": f"Schedule {schedule_id} not found"}),
            404,
        )
    return jsonify(_progress_to_dict(schedule))
