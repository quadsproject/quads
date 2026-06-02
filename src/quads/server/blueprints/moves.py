from datetime import datetime

from flask import Blueprint, Response, jsonify, make_response, request

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import EntryNotFound
from quads.server.dao.host import HostDao
from quads.server.dao.move_progress import MoveProgressDao
from quads.server.dao.schedule import ScheduleDao

moves_bp = Blueprint("moves", __name__)


def _progress_to_dict(progress):
    return {
        "id": progress.id,
        "host": progress.host.name,
        "host_id": progress.host_id,
        "source_cloud": progress.source_cloud,
        "target_cloud": progress.target_cloud,
        "status": progress.status if progress.status else "pending",
        "message": progress.message,
        "error_message": progress.error_message,
        "started_at": progress.started_at.isoformat() if progress.started_at else None,
        "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
        "schedule_id": progress.schedule_id,
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
def get_all_move_progress() -> Response:
    cloud = request.args.get("cloud")
    status = request.args.get("status")
    moves = MoveProgressDao.get_all_active(cloud=cloud, status=status)
    return jsonify([_progress_to_dict(m) for m in moves])


@moves_bp.route("/progress/<hostname>")
def get_move_progress(hostname: str) -> Response:
    progress = MoveProgressDao.get_active_by_hostname(hostname)
    if not progress:
        return make_response(
            jsonify({"error": "Not Found", "message": f"No active move for {hostname}"}),
            404,
        )
    return jsonify(_progress_to_dict(progress))


@moves_bp.route("/progress/", methods=["POST"])
@check_access(["admin"])
def create_move_progress() -> Response:
    data = request.get_json()
    hostname = data.get("hostname")
    if not hostname:
        return make_response(
            jsonify({"error": "Bad Request", "message": "hostname is required"}),
            400,
        )
    host = HostDao.get_host(hostname)
    if not host:
        return make_response(
            jsonify({"error": "Not Found", "message": f"Host {hostname} not found"}),
            404,
        )
    progress = MoveProgressDao.create_move_progress(
        host_id=host.id,
        source_cloud=data.get("source_cloud", ""),
        target_cloud=data.get("target_cloud", ""),
        schedule_id=data.get("schedule_id"),
    )
    return make_response(jsonify(_progress_to_dict(progress)), 201)


@moves_bp.route("/progress/batch", methods=["POST"])
@check_access(["admin"])
def create_move_progress_batch() -> Response:
    data = request.get_json()
    records = data.get("records", [])
    if not records:
        return make_response(
            jsonify({"error": "Bad Request", "message": "records list is required"}),
            400,
        )
    result = MoveProgressDao.create_move_progress_batch(records)
    return make_response(jsonify(result), 201)


@moves_bp.route("/progress/<int:progress_id>", methods=["PATCH"])
@check_access(["admin"])
def update_move_progress(progress_id: int) -> Response:
    data = request.get_json()
    allowed_fields = {"status", "message", "error_message"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    try:
        progress = MoveProgressDao.update_progress(progress_id, **update_data)
    except EntryNotFound:
        return make_response(
            jsonify({"error": "Not Found", "message": f"Progress record {progress_id} not found"}),
            404,
        )
    return jsonify(_progress_to_dict(progress))
