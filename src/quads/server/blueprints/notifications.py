from flask import Blueprint, jsonify, request, Response, make_response
from sqlalchemy import inspect

from quads.server.blueprints import check_access
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.notification import NotificationDao
from quads.server.models import Notification

notification_bp = Blueprint("notifications", __name__)


@notification_bp.route("/")
def get_all_notifications() -> Response:
    _notifications = NotificationDao.get_notifications()
    return jsonify([_notification.as_dict() for _notification in _notifications])


@notification_bp.route("/<notification_id>")
def get_notification(notification_id: int) -> Response:
    _notification = NotificationDao.get_notification(notification_id)
    if not _notification:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Notification not found: {notification_id}",
        }
        return make_response(jsonify(response), 400)

    return jsonify(_notification.as_dict())


@notification_bp.route("/<notification_id>", methods=["PATCH"])
@check_access(["admin"])
def update_notification(notification_id: int) -> Response:
    notification_obj = NotificationDao.get_notification(notification_id)
    if not notification_obj:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"Notification not found: {notification_id}",
        }
        return make_response(jsonify(response), 400)
    data = request.get_json()

    obj_attrs = inspect(Notification).mapper.attrs
    update_fields = {}
    for attr in obj_attrs:
        value = data.get(attr.key)
        if attr.key in data:
            if isinstance(value, str):
                if value.lower() in ["true", "false"]:
                    value = eval(value.lower().capitalize())
            update_fields[attr.key] = value

    for key, value in update_fields.items():
        setattr(notification_obj, key, value)

    BaseDao.safe_commit()
    return jsonify(notification_obj.as_dict())
