import json

from flask import Blueprint, Response, jsonify, make_response, request

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.disk import DiskDao
from quads.server.dao.host import HostDao
from quads.server.models import Disk, db

disk_bp = Blueprint("disks", __name__)


@disk_bp.route("/")
def get_all_disks() -> Response:
    _disks = DiskDao.get_disks()
    return jsonify([_disk.as_dict() for _disk in _disks])


@disk_bp.route("/<disk_id>")
def get_disk(disk_id: int) -> Response:
    _disk = DiskDao.get_disk(disk_id)
    if not _disk:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Disk not found: {disk_id}",
        }
        return make_response(jsonify(response), 400)
    return jsonify(_disk.as_dict())


@disk_bp.route("/<hostname>", methods=["POST"])
@check_access(["admin"])
def create_disks(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    data = request.get_json()

    disk_type = data.get("disk_type")
    size_gb = data.get("size_gb")
    count = data.get("count")

    if not disk_type:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: disk_type",
        }
        return make_response(jsonify(response), 400)

    if not size_gb:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: size_gb",
        }
        return make_response(jsonify(response), 400)

    if not count:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: count",
        }
        return make_response(jsonify(response), 400)

    if not count > 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: count",
        }
        return make_response(jsonify(response), 400)

    if size_gb <= 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: size_gb",
        }
        return make_response(jsonify(response), 400)

    _disk_obj = Disk(disk_type=disk_type, size_gb=size_gb, count=count, host_id=_host.id)
    db.session.add(_disk_obj)
    BaseDao.safe_commit()
    return jsonify(_disk_obj.as_dict())


@disk_bp.route("/<hostname>", methods=["PATCH"])
@check_access(["admin"])
def update_disk(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    data = request.get_json()
    disk_id = data.get("disk_id")
    disk_object = DiskDao.get_disk(disk_id)
    if not disk_object:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Disk not found for {hostname}: {disk_id}",
        }
        return Response(response=json.dumps(response), status=400)

    update_fields = {}
    keys = ["disk_type", "size_gb", "count"]
    for key in keys:
        value = data.get(key)
        if value:
            update_fields[key] = value

    if update_fields.get("count") and int(update_fields.get("count")) <= 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: count",
        }
        return make_response(jsonify(response), 400)

    if update_fields.get("size_gb") and int(update_fields.get("size_gb")) <= 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: size_gb",
        }
        return make_response(jsonify(response), 400)

    for key, value in update_fields.items():
        setattr(disk_object, key, value)
    BaseDao.safe_commit()
    return jsonify(disk_object.as_dict())


@disk_bp.route("/<disk_id>", methods=["DELETE"])
@check_access(["admin"])
def delete_disk(disk_id: int) -> Response:
    _disk_obj = DiskDao.get_disk(disk_id)
    if not _disk_obj:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Disk not found: {disk_id}",
        }
        return make_response(jsonify(response), 400)

    db.session.delete(_disk_obj)
    BaseDao.safe_commit()
    response = {
        "status_code": 200,
        "message": "Disk deleted",
    }
    return jsonify(response)
