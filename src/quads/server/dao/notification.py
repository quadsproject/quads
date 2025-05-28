from typing import List

from quads.server.dao.baseDao import BaseDao, SQLError
from quads.server.models import Notification, db


class NotificationDao(BaseDao):
    @staticmethod
    def get_notifications() -> List[Notification]:  # pragma: no cover
        notifications = db.session.query(Notification).all()
        return notifications

    @staticmethod
    def get_notification(notification_id: int) -> Notification:  # pragma: no cover
        processor = db.session.query(Notification).filter(Notification.id == notification_id).first()
        return processor

    @staticmethod
    def get_assignment_notification(
        assignment_id: int,
    ) -> Notification:  # pragma: no cover
        processors = db.session.query(Notification).filter(Notification.assignment_id == assignment_id).first()
        return processors

    @classmethod
    def update_notification(
        cls,
        notification_id: int,
        fail: bool = None,
        success: bool = None,
        initial: bool = None,
        pre_initial: bool = None,
        pre: bool = None,
        one_day: bool = None,
        three_days: bool = None,
        five_days: bool = None,
        seven_days: bool = None,
    ) -> Notification:  # pragma: no cover
        notification = db.session.query(Notification).filter(Notification.id == notification_id).first()

        _flags = {
            "fail": fail,
            "success": success,
            "initial": initial,
            "pre_initial": pre_initial,
            "pre": pre,
            "one_day": one_day,
            "three_days": three_days,
            "five_days": five_days,
            "seven_days": seven_days,
        }
        for key, value in _flags.items():
            if value is not None:
                setattr(notification, key, value)

        result = cls.safe_commit()
        if not result:
            raise SQLError("Failed to update notification")

        return notification
