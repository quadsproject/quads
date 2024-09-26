from typing import List

from quads.server.dao.baseDao import BaseDao
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
