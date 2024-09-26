from flask import Blueprint, Response, jsonify, make_response, request

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.vlan import VlanDao
from quads.server.models import Vlan, db

vlan_bp = Blueprint("vlans", __name__)


@vlan_bp.route("/<vlan_id>")
def get_vlan(vlan_id: int) -> Response:
    _vlan = VlanDao.get_vlan(vlan_id)
    if not _vlan:
        status_code = 400
        response = {
            "status_code": status_code,
            "error": "Entry not found",
            "message": f"Vlan not found: {vlan_id}",
        }
        return make_response(jsonify(response), status_code)

    return jsonify(_vlan.as_dict())


@vlan_bp.route("/")
def get_vlans() -> Response:
    _vlans = VlanDao.get_vlans()
    return jsonify([_vlan.as_dict() for _vlan in _vlans])


@vlan_bp.route("/", methods=["POST"])
@check_access(["admin"])
def create_vlan() -> Response:
    data = request.get_json()
    gateway = data.get("gateway")
    ip_free = data.get("ip_free")
    ip_range = data.get("ip_range")
    netmask = data.get("netmask")
    vlan_id = data.get("vlan_id")

    required_fields = [
        "gateway",
        "ip_free",
        "ip_range",
        "netmask",
        "vlan_id",
    ]
    for field in required_fields:
        if not data.get(field):
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Missing argument: {field}",
            }
            return make_response(jsonify(response), 400)

    _vlan = VlanDao.get_vlan(vlan_id)
    if _vlan:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Vlan {vlan_id} already exists",
        }
        return make_response(jsonify(response), 400)

    _vlan_obj = Vlan(
        gateway=gateway,
        ip_free=ip_free,
        ip_range=ip_range,
        netmask=netmask,
        vlan_id=vlan_id,
    )
    db.session.add(_vlan_obj)
    BaseDao.safe_commit()
    return jsonify(_vlan_obj.as_dict())


@vlan_bp.route("/<vlan_id>", methods=["DELETE"])
@check_access(["admin"])
def delete_vlan(vlan_id: int) -> Response:
    _vlan_obj = VlanDao.get_vlan(vlan_id)
    if not _vlan_obj:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Vlan not found: {vlan_id}",
        }
        return make_response(jsonify(response), 400)

    db.session.delete(_vlan_obj)
    BaseDao.safe_commit()
    response = {
        "status_code": 200,
        "message": "Vlan deleted",
    }
    return jsonify(response)


@vlan_bp.route("/<vlan_id>", methods=["PATCH"])
@check_access(["admin"])
def update_vlan(vlan_id: int) -> Response:
    data = request.get_json()
    gateway = data.get("gateway")
    ip_free = data.get("ip_free")
    ip_range = data.get("ip_range")
    netmask = data.get("netmask")

    _vlan = VlanDao.get_vlan(vlan_id)
    if not _vlan:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Vlan not found: {vlan_id}",
        }
        return make_response(jsonify(response), 400)

    if gateway:
        _vlan.gateway = gateway
    if ip_free:
        _vlan.ip_free = ip_free
    if ip_range:
        _vlan.ip_range = ip_range
    if netmask:
        _vlan.netmask = netmask

    BaseDao.safe_commit()

    return jsonify(_vlan.as_dict())
