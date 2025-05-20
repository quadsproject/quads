import json
from datetime import datetime

from flask import Blueprint, Response, jsonify, make_response, request

from quads.config import Config
from quads.server.blueprints import check_access
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import EntryNotFound, InvalidArgument
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao

cloud_bp = Blueprint("clouds", __name__)


@cloud_bp.route("/")
def get_clouds() -> Response:
    """
    Returns a list of all clouds in the database.
        ---
        tags:
          - API

    :return: The list of clouds
    """
    if request.args:
        try:
            _clouds = CloudDao.filter_clouds_dict(request.args)
        except (EntryNotFound, InvalidArgument) as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    else:
        _clouds = CloudDao.get_clouds()
    return jsonify([_cloud.as_dict() for _cloud in _clouds] if _clouds else {})


@cloud_bp.route("/free/")
def get_free_clouds() -> Response:
    """
    Returns a list of all free clouds in the database.
        ---
        tags:
          - API

    :return: The list of free clouds
    """
    _clouds = CloudDao.get_free_clouds()

    return jsonify([_cloud.as_dict() for _cloud in _clouds])


@cloud_bp.route("/", methods=["POST"])
@check_access(["admin"])
def create_cloud() -> Response:
    """
    Creates a new cloud in the database.
        ---
        tags:
          - API

    :return: A response object with the created cloud
    """
    data = request.get_json()
    cloud_name = data.get("cloud")
    if not cloud_name:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: cloud",
        }
        return Response(response=json.dumps(response), status=400)

    _cloud = CloudDao.get_cloud(cloud_name)
    if _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud {cloud_name} already exists",
        }
        return Response(response=json.dumps(response), status=400)

    _cloud_obj = CloudDao.create_cloud(cloud_name)
    return jsonify(_cloud_obj.as_dict())


@cloud_bp.route("/<cloud>/", methods=["PATCH"])
@check_access(["admin"])
def update_cloud(cloud) -> Response:
    """
    Updates an exiting cloud in the database.
        ---
        tags:
          - API

    :return: A response object with the created cloud
    """

    _cloud = CloudDao.get_cloud(cloud)
    if not _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud {cloud} does not exist",
        }
        return Response(response=json.dumps(response), status=400)

    data = request.get_json()
    parsed_data = {}
    name = data.get("name")
    if name:
        parsed_data["name"] = name
    last_redefined = data.get("last_redefined")
    _format = "%Y-%m-%dT%H:%M"
    try:
        if last_redefined:
            last_redefined = datetime.strptime(last_redefined, _format)
            parsed_data["last_redefined"] = last_redefined
    except ValueError:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'",
        }
        return make_response(jsonify(response), 400)

    _cloud_obj = CloudDao.update_cloud(cloud, **data)
    return jsonify(_cloud_obj.as_dict())


@cloud_bp.route("/<cloud>/", methods=["DELETE"])
@check_access(["admin"])
def delete_cloud(cloud: str) -> Response:
    """
    Deletes a cloud from the database.
        Args:
            cloud (str): The name of the cloud to delete.

    :param cloud: str: Specify the name of the cloud to be deleted
    :return: A response object with a 204 status code
    """

    _cloud = CloudDao.get_cloud(cloud)
    if not _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud not found: {cloud}",
        }
        return make_response(jsonify(response), 400)
    CloudDao.remove_cloud(cloud)
    response = {
        "status_code": 200,
        "message": f"Cloud {cloud} deleted",
    }
    return jsonify(response)


@cloud_bp.route("/summary/")
def get_summary() -> Response:
    """
    Gets a cloud summary.

    :param date: str: A date in the past for a time-bound summary
    :return: A response object with a 200 status code
    """

    data = request.args.to_dict()
    _date = data.get("date")
    clouds_summary = []
    total_count = 0
    _clouds = CloudDao.get_clouds()
    for _cloud in _clouds:
        _assignment = None
        description = "Available"
        owner = ""
        if _cloud.name == "cloud01":
            hosts = HostDao.filter_hosts(cloud=_cloud, retired=False, broken=False)
            count = len(hosts)
            description = Config["spare_pool_description"]
            owner = Config["spare_pool_owner"]
        else:
            date = datetime.strptime(_date, "%Y-%m-%dT%H:%M") if _date else datetime.now()
            schedules = ScheduleDao.get_current_schedule(cloud=_cloud, date=date)
            count = len(schedules)
            total_count += count
            if schedules:
                _assignment = AssignmentDao.get_assignment(schedules[0].assignment_id)
            else:
                _assignment = AssignmentDao.get_active_cloud_assignment(_cloud)

        clouds_summary.append(
            {
                "name": _cloud.name,
                "count": count,
                "description": _assignment.description if _assignment else description,
                "owner": _assignment.owner if _assignment else owner,
                "ticket": _assignment.ticket if _assignment else "",
                "ccuser": _assignment.ccuser if _assignment else "",
                "provisioned": _assignment.provisioned if _assignment else False,
                "validated": _assignment.validated if _assignment else False,
                "is_self_schedule": _assignment.is_self_schedule if _assignment else False,
            }
        )

    return jsonify(clouds_summary)
