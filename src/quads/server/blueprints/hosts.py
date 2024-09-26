from flask import Blueprint, Response, jsonify, make_response, request
from sqlalchemy import inspect

from quads.config import Config
from quads.server.blueprints import check_access
from quads.server.dao.baseDao import BaseDao, EntryNotFound, InvalidArgument
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.models import Host, db

host_bp = Blueprint("hosts", __name__)


@host_bp.route("/")
def get_hosts() -> Response:
    if request.args:
        try:
            _hosts = HostDao.filter_hosts_dict(request.args)
        except (EntryNotFound, InvalidArgument) as ex:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": str(ex),
            }
            return make_response(jsonify(response), 400)

    else:
        _hosts = HostDao.get_hosts()

    if _hosts and type(_hosts[0]) is Host:
        return jsonify([_host.as_dict() for _host in _hosts])
    else:
        for _host in _hosts:
            return jsonify([tuple(_host) for _host in _hosts])

    return jsonify(_hosts)


@host_bp.route("/<hostname>")
def get_host(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    return jsonify(_host.as_dict())


@host_bp.route("/<hostname>/memory")
def get_host_memory(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    return jsonify([_memory.as_dict() for _memory in _host.memory])


@host_bp.route("/<hostname>/processors")
def get_host_processors(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    return jsonify([_processors.as_dict() for _processors in _host.processors])


@host_bp.route("/<hostname>/disks")
def get_host_disks(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    return jsonify([_disks.as_dict() for _disks in _host.disks])


@host_bp.route("/<hostname>/interfaces")
def get_host_interfaces(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)
    return jsonify([_interface.as_dict() for _interface in _host.interfaces])


@host_bp.route("/<hostname>", methods=["PATCH"])
@check_access(["admin"])
def update_host(hostname: str) -> Response:
    data = request.get_json()

    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)

    obj_attrs = inspect(Host).mapper.attrs
    update_fields = {}
    for attr in obj_attrs:
        value = data.get(attr.key)
        if value is not None:
            if attr.key.lower() in ["cloud", "default_cloud"]:
                _cloud = CloudDao.get_cloud(value)
                if not _cloud:
                    response = {
                        "status_code": 400,
                        "error": "Bad Request",
                        "message": f"Cloud not found: {value}",
                    }
                    return make_response(jsonify(response), 400)

                value = _cloud
            if attr.key.lower() == "model":
                _host.model = value.upper()
            if type(value) is str:
                if value.lower() in ["true", "false"]:
                    value = eval(value.lower().capitalize())
            update_fields[attr.key] = value

    for key, value in update_fields.items():
        setattr(_host, key, value)

    BaseDao.safe_commit()

    return jsonify(_host.as_dict())


@host_bp.route("/", methods=["POST"])
@check_access(["admin"])
def create_host() -> Response:
    data = request.get_json()
    hostname = data.get("name")
    model = data.get("model")
    default_cloud = data.get("default_cloud")
    host_type = data.get("host_type")
    can_self_schedule = data.get("can_self_schedule")

    if not model:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: model",
        }
        return make_response(jsonify(response), 400)
    else:
        if model.upper() not in Config["models"]:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Model {model} does not seem to be part of the defined models on quads.yml",
            }
            return make_response(jsonify(response), 400)

    if not default_cloud:
        default_cloud = Config["spare_pool_name"]

    if not hostname:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: name",
        }
        return make_response(jsonify(response), 400)

    _host = HostDao.get_host(hostname)
    if _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host {hostname} already exists",
        }
        return make_response(jsonify(response), 400)

    if not host_type:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: host_type",
        }
        return make_response(jsonify(response), 400)

    if default_cloud:
        _default_cloud = CloudDao.get_cloud(default_cloud)
        if not _default_cloud:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Default Cloud not found: {default_cloud}",
            }
            return make_response(jsonify(response), 400)

    else:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Missing argument: default_cloud",
        }
        return make_response(jsonify(response), 400)

    _host_obj = Host(
        name=hostname,
        model=model.upper(),
        host_type=host_type,
        can_self_schedule=can_self_schedule,
        default_cloud=_default_cloud,
        cloud=_default_cloud,
    )
    db.session.add(_host_obj)
    BaseDao.safe_commit()
    return jsonify(_host_obj.as_dict())


@host_bp.route("/<hostname>", methods=["DELETE"])
@check_access(["admin"])
def delete_host(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)

    HostDao.remove_host(hostname)
    response = {
        "status_code": 200,
        "message": "Host deleted",
    }
    return jsonify(response)
