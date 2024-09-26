import re
from datetime import datetime

from flask import Blueprint, Response, jsonify, make_response, request
from sqlalchemy import inspect

from quads.config import Config
from quads.server.blueprints import check_access
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import BaseDao, EntryNotFound, InvalidArgument
from quads.server.dao.cloud import CloudDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from quads.server.models import Assignment

assignment_bp = Blueprint("assignments", __name__)


@assignment_bp.route("/")
def get_assignments() -> Response:
    """
    Returns a list of all assignments in the database.
        ---
        tags:
          - Assignment API

    :return: A list of all assignments in the database
    """
    if request.args:
        try:
            _assignments = AssignmentDao.filter_assignments(request.args)
        except (EntryNotFound, InvalidArgument) as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    else:
        _assignments = AssignmentDao.get_assignments()
    return jsonify([_assignment.as_dict() for _assignment in _assignments])


@assignment_bp.route("/<assignment_id>/")
def get_assignment(assignment_id: str) -> Response:
    """
    Used to retrieve a single assignment from the database.
        It takes in an assignment_id as a parameter and returns the corresponding Assignment object.
        If no such Assignment exists, it will return a 400 Bad Request error.
        ---
        tags:
          - Assignment API

    :param assignment_id: Get the assignment from the database
    :return: The assignment as a json object
    """
    _assignment = AssignmentDao.get_assignment(int(assignment_id))
    if not _assignment:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Assignment not found: {assignment_id}",
        }
        return make_response(jsonify(response), 400)
    return jsonify(_assignment.as_dict())


@assignment_bp.route("/active/<cloud_name>/")
def get_active_cloud_assignment(cloud_name: str) -> Response:
    """
    Returns the active assignment for a given cloud.
        ---
        tags:
          - Assignment API

    :param cloud_name: Find the cloud in the database
    :return: The active assignment for the cloud
    """
    _cloud = CloudDao.get_cloud(cloud_name)
    if not _cloud:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Cloud not found: {cloud_name}",
        }
        return make_response(jsonify(response), 400)
    _assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
    response = {}
    if _assignment:
        response = _assignment.as_dict()
    return jsonify(response)


@assignment_bp.route("/active/")
def get_active_assignments() -> Response:
    """
    Returns all active assignments.
        ---
        tags:
          - Assignment API

    :return: A list of all active assignments
    """
    _assignments = AssignmentDao.get_active_assignments()
    response = []
    if _assignments:
        for _ass in _assignments:
            response.append(_ass.as_dict())
    return jsonify(response)


@assignment_bp.route("/", methods=["POST"])
@check_access(["admin"])
def create_assignment() -> Response:
    """
    Creates a new assignment in the database.
        ---
        tags:
          - API

    :return: The created object as a json
    """
    data = request.get_json()

    _cloud = None
    _vlan = None
    cloud_name = data.get("cloud")
    vlan = data.get("vlan")
    description = data.get("description")
    owner = data.get("owner")
    ticket = data.get("ticket")
    qinq = data.get("qinq")
    wipe = data.get("wipe")
    cc_user = data.get("ccuser")
    is_self_schedule = data.get("is_self_schedule")

    required_fields = [
        "description",
        "owner",
        "ticket",
        "cloud",
    ]
    for field in required_fields:
        if not data.get(field):
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Missing argument: {field}",
            }
            return make_response(jsonify(response), 400)

    if cc_user:
        cc_user = re.split(r"[, ]+", cc_user)

    if cloud_name:
        _cloud = CloudDao.get_cloud(cloud_name)
        if not _cloud:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Cloud not found: {cloud_name}",
            }
            return make_response(jsonify(response), 400)
        _assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
        if _assignment:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"There is an already active assignment for {cloud_name}",
            }
            return make_response(jsonify(response), 400)

    if vlan:
        _vlan = VlanDao.get_vlan(int(vlan))
        if not _vlan:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Vlan not found: {vlan}",
            }
            return make_response(jsonify(response), 400)

    kwargs = {
        "description": description,
        "owner": owner,
        "ticket": ticket,
        "qinq": qinq,
        "wipe": wipe,
        "ccuser": cc_user,
        "cloud": cloud_name,
        "is_self_schedule": is_self_schedule,
    }
    if _vlan:
        kwargs["vlan_id"] = int(vlan)
    _assignment_obj = AssignmentDao.create_assignment(**kwargs)
    return jsonify(_assignment_obj.as_dict())


@assignment_bp.route("/self/", methods=["POST"])
@check_access(["user"])
def create_self_assignment() -> Response:
    """
    Creates a new self assignment in the database.
        ---
        tags:
          - API

    :return: The created object as a json
    """
    data = request.get_json()

    enabled = Config.get("ssm_enable", False)
    if not enabled:
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": "Service not enabled",
        }
        return make_response(jsonify(response), 403)

    active_ass = AssignmentDao.filter_assignments(
        {"active": True, "is_self_schedule": True, "owner": data.get("owner")}
    )
    if len(active_ass) >= Config.get("ssm_user_cloud_limit", 1):
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": "Self scheduling limit reached",
        }
        return make_response(jsonify(response), 403)

    _cloud = None
    _vlan = None
    cloud_name = data.get("cloud")
    vlan = data.get("vlan")
    description = data.get("description")
    owner = data.get("owner")
    ticket = data.get("ticket")
    qinq = data.get("qinq")
    wipe = data.get("wipe")
    cc_user = data.get("cc_user")

    required_fields = [
        "description",
        "owner",
    ]

    for field in required_fields:
        if not data.get(field):
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Missing argument: {field}",
            }
            return make_response(jsonify(response), 400)

    if cc_user:
        cc_user = re.split(r"[, ]+", cc_user)

    if cloud_name:
        _cloud = CloudDao.get_cloud(cloud_name)
        if not _cloud:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Cloud not found: {cloud_name}",
            }
            return make_response(jsonify(response), 400)
        _assignment = AssignmentDao.get_active_cloud_assignment(_cloud)
        if _assignment:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"There is an already active assignment for {cloud_name}",
            }
            return make_response(jsonify(response), 400)
    else:
        _free_clouds = CloudDao.get_free_clouds()
        if not _free_clouds:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": "No free clouds available",
            }
            return make_response(jsonify(response), 400)
        _cloud = _free_clouds[0]

    if vlan:
        _vlan = VlanDao.get_vlan(int(vlan))
        if not _vlan:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Vlan not found: {vlan}",
            }
            return make_response(jsonify(response), 400)

    kwargs = {
        "description": description,
        "owner": owner,
        "ticket": ticket,
        "qinq": qinq,
        "wipe": wipe,
        "ccuser": cc_user,
        "is_self_schedule": True,
        "cloud": _cloud.name,
    }
    if _vlan:
        kwargs["vlan_id"] = int(vlan)
    _assignment_obj = AssignmentDao.create_assignment(**kwargs)
    return jsonify(_assignment_obj.as_dict())


@assignment_bp.route("/<assignment_id>/", methods=["PATCH"])
@check_access(["admin"])
def update_assignment(assignment_id: str) -> Response:
    """
    Updates an existing assignment.
        ---
        tags: API
        parameters:
          - in: path
            name: assignment_id  # The id of the assignment to update. This is a required parameter.
                It must be passed as part of the URL path, not as a query string or request body parameter.

    :param assignment_id: str: Identify which assignment to update
    :return: A json object containing the updated assignment
    """
    data = request.get_json()
    assignment_obj = AssignmentDao.get_assignment(int(assignment_id))
    if not assignment_obj:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Assignment not found: {assignment_id}",
        }
        return make_response(jsonify(response), 400)

    obj_attrs = inspect(Assignment).mapper.attrs
    update_fields = {}
    for _key, _value in data.items():
        value = _value
        if _key not in [attr.key for attr in obj_attrs]:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Invalid argument: {_key}",
            }
            return make_response(jsonify(response), 400)
        if _key == "ccuser":
            value = re.split(r"[, ]+", _value)
            value = [user.strip() for user in value]
        if _key == "cloud":
            _cloud = CloudDao.get_cloud(_value)
            if not _cloud:
                response = {
                    "status_code": 400,
                    "error": "Bad Request",
                    "message": f"Cloud not found: {_value}",
                }
                return make_response(jsonify(response), 400)
            value = _cloud
        if _key == "vlan":
            kambiz_none_values = ["none", "0", "no", "nada", "clear"]
            value = None
            if _value and str(_value).lower() not in kambiz_none_values:
                _vlan = VlanDao.get_vlan(_value)
                if not _vlan:
                    response = {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": f"Vlan not found: {_value}, for clearing use any of: {kambiz_none_values}",
                    }
                    return make_response(jsonify(response), 400)
                value = _vlan
        if type(_value) is str:
            if _value.lower() in ["true", "false"]:
                value = eval(_value.lower().capitalize())
        update_fields[_key] = value

    for key, value in update_fields.items():
        setattr(assignment_obj, key, value)

    BaseDao.safe_commit()
    return jsonify(assignment_obj.as_dict())


@assignment_bp.route("/terminate/<assignment_id>/", methods=["POST"])
@check_access(["user"])
def terminate_assignment(assignment_id) -> Response:
    """
    Terminates an existing assignment.
        ---
        tags: API
        parameters:
          - in: path
            name: assignment_id
    """
    _assignment = AssignmentDao.get_assignment(int(assignment_id))
    if not _assignment:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Assignment not found: {assignment_id}",
        }
        return make_response(jsonify(response), 400)

    auth_value = request.headers["Authorization"].split(" ")
    user = auth_value[1].split("@")[0]
    if user != _assignment.owner:
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": "You don't have permission to terminate this assignment",
        }
        return make_response(jsonify(response), 403)

    _schedules = ScheduleDao.get_current_schedule(cloud=_assignment.cloud)
    if not _schedules:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"No active schedule for {assignment_id}",
        }
        return make_response(jsonify(response), 400)

    for sched in _schedules:
        sched.end = datetime.now()

    BaseDao.safe_commit()

    response = {
        "status_code": 200,
        "message": "Assignment terminated",
    }
    return jsonify(response)


@assignment_bp.route("/", methods=["DELETE"])
@check_access(["admin"])
def delete_assignment() -> Response:
    """
    Used to delete an assignment from the database.
    It takes in a JSON object with one key, &quot;id&quot;, which corresponds to the id of the assignment that
    will be deleted.
    If no such assignment exists, it returns a 400 error code and message explaining that there was no such entry
    found.
    Otherwise, it deletes the entry and returns a 204 status code.

    :return: A response with a status code of 204
    """
    data = request.get_json()
    assignment_id = data.get("id")
    if not assignment_id:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: id",
        }
        return make_response(jsonify(response), 400)

    try:
        AssignmentDao.delete_assignment(assignment_id)
    except EntryNotFound:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Assignment not found: {assignment_id}",
        }
        return make_response(jsonify(response), 400)
    response = {
        "status_code": 200,
        "message": "Assignment deleted",
    }
    return jsonify(response)
