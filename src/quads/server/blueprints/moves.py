from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, make_response, request

from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao

moves_bp = Blueprint("moves", __name__)


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
