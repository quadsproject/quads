from flask import Blueprint, Response, jsonify, make_response, request

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.host import HostDao
from quads.server.dao.processor import ProcessorDao
from quads.server.models import Processor, db

processor_bp = Blueprint("processors", __name__)


@processor_bp.route("/")
def get_all_processors() -> Response:
    _processors = ProcessorDao.get_processors()
    return jsonify([_processor.as_dict() for _processor in _processors])


@processor_bp.route("/<processor_id>")
def get_processor(processor_id: int) -> Response:
    _processor = ProcessorDao.get_processor(processor_id)
    if not _processor:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Processor not found: {processor_id}",
        }
        return make_response(jsonify(response), 400)

    return jsonify(_processor.as_dict())


@processor_bp.route("/<hostname>", methods=["POST"])
@check_access(["admin"])
def create_processor(hostname: str) -> Response:
    _host = HostDao.get_host(hostname)
    if not _host:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Host not found: {hostname}",
        }
        return make_response(jsonify(response), 400)

    data = request.get_json()

    handle = data.get("handle")
    vendor = data.get("vendor")
    product = data.get("product")
    cores = data.get("cores")
    threads = data.get("threads")
    required_fields = [
        "handle",
        "vendor",
        "product",
        "cores",
        "threads",
    ]
    for field in required_fields:
        if not data.get(field):
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": f"Missing argument: {field}",
            }
            return make_response(jsonify(response), 400)

    if not cores > 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: cores",
        }
        return make_response(jsonify(response), 400)

    if not threads > 0:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Argument can't be negative or zero: threads",
        }
        return make_response(jsonify(response), 400)

    processors = ProcessorDao.get_processor_for_host(_host.id)
    if any(processor.handle == handle for processor in processors):
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Processor with this handle ({handle}) already exists for this host.",
        }
        return make_response(jsonify(response), 400)

    _processor_obj = Processor(
        handle=handle,
        vendor=vendor,
        product=product,
        cores=cores,
        threads=threads,
        host_id=_host.id,
    )
    db.session.add(_processor_obj)
    BaseDao.safe_commit()
    return jsonify(_processor_obj.as_dict())


@processor_bp.route("/<processor_id>", methods=["DELETE"])
@check_access(["admin"])
def delete_processor(processor_id: int) -> Response:
    _processor_obj = ProcessorDao.get_processor(processor_id)
    if not _processor_obj:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Processor not found: {processor_id}",
        }
        return make_response(jsonify(response), 400)

    db.session.delete(_processor_obj)
    BaseDao.safe_commit()
    response = {
        "status_code": 200,
        "message": "Processor deleted",
    }
    return jsonify(response)
