from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, make_response, request

from quads.helpers.selfservice import ssm_remaining_capacity
from quads.server.dao.baseDao import EntryNotFound, InvalidArgument
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao

available_bp = Blueprint("available", __name__)


def _is_ss_view(params) -> bool:
    raw = params.get("can_self_schedule")
    return raw is not None and str(raw).lower() in ("true", "y", "yes")


@available_bp.route("/", methods=["GET"])
def get_available() -> Response:
    """
    Used to return a list of hosts that are available for the given time period.
        ---
        tags:
          - Hosts

    :return: A list of hosts that are available for the given start and end time
    """
    _params = request.args.to_dict()
    _start = _end = datetime.now()
    _cloud = None
    if "cloud" in _params:
        _cloud = _params.pop("cloud")
    try:
        start = None
        end = None
        if "start" in _params:
            start = _params.pop("start")
        if start:
            _start = datetime.strptime(start, "%Y-%m-%dT%H:%M")
        if "end" in _params:
            end = _params.pop("end")
        if end:
            _end = datetime.strptime(end, "%Y-%m-%dT%H:%M")
    except ValueError:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'",
        }
        return make_response(jsonify(response), 400)

    if _start > _end:
        _end = _start + timedelta(minutes=1)

    if _params:
        try:
            all_hosts = HostDao.filter_hosts_dict(_params)
        except (EntryNotFound, InvalidArgument) as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    else:
        all_hosts = HostDao.get_hosts()

    available = []
    for host in all_hosts:
        if ScheduleDao.is_host_available(host.name, _start, _end):
            if _cloud:
                _sched_cloud = ScheduleDao.get_current_schedule(host=host)
                _sched_cloud = _sched_cloud[0].assignment.cloud.name if _sched_cloud else None
                if _cloud != _sched_cloud:
                    continue
            available.append(host.name)

    if _is_ss_view(_params):
        remaining_per_model = {}
        capped = []
        for host in all_hosts:
            if host.name not in available:
                continue
            model = host.model
            if model not in remaining_per_model:
                remaining_per_model[model] = max(0, ssm_remaining_capacity(model, _start, _end))
            if remaining_per_model[model] > 0:
                capped.append(host.name)
                remaining_per_model[model] -= 1
        return jsonify(capped)
    return jsonify(available)


@available_bp.route("/<hostname>")
def is_available(hostname) -> Response:
    """
    Used to determine if a host is available for a given time period.
        The function takes in the following parameters:
            - hostname (string): The name of the host that you want to check availability for.
            - start (datetime): A datetime object representing when you would like your reservation to begin.
            If no value is provided, it will default to now().
            - end (datetime): A datetime object representing when you would like your reservation to end.
            If no value is provided, it will default to now().

    :param hostname: Specify the hostname of the device
    :return: A boolean value
    """
    _params = request.args.to_dict()
    _start = _end = datetime.now()
    if _params.get("start"):
        try:
            _start = datetime.strptime(_params.get("start"), "%Y-%m-%dT%H:%M")
        except ValueError:
            return make_response(
                jsonify(
                    {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'",
                    }
                ),
                400,
            )
    if _params.get("end"):
        try:
            _end = datetime.strptime(_params.get("end"), "%Y-%m-%dT%H:%M")
        except ValueError:
            return make_response(
                jsonify(
                    {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'",
                    }
                ),
                400,
            )
    if _start > _end:
        _end = _start + timedelta(minutes=1)

    available = ScheduleDao.is_host_available(hostname, _start, _end)
    return jsonify({hostname: str(available)})
