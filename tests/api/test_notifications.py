import pytest

from quads.server.dao.notification import NotificationDao
from quads.server.models import Assignment, Cloud, Notification, db


@pytest.fixture
def assignments(test_client):
    clouds = [Cloud(name="cloud01"), Cloud(name="cloud02")]
    assignments = [
        Assignment(id=101, cloud=clouds[0], notification=Notification(id=202, fail=True)),
        Assignment(id=202, cloud=clouds[1], notification=Notification(id=101, success=True)),
    ]
    db.session.add_all(assignments)
    db.session.commit()
    yield assignments
    db.session.rollback()
    for assignment in assignments:
        db.session.delete(assignment)
    for cloud in clouds:
        db.session.delete(cloud)
    db.session.commit()


@pytest.mark.parametrize("assignment_index", [0, 1])
def test_get_notification_by_id(test_client, assignments, assignment_index):
    notification = assignments[assignment_index].notification

    response = test_client.get(f"/api/v3/notifications/{notification.id}")

    assert response.status_code == 200
    assert response.json == notification.as_dict()


def test_dao_distinguishes_notification_and_assignment_ids(assignments):
    assert NotificationDao.get_notification(101) is assignments[1].notification
    assert NotificationDao.get_assignment_notification(101) is assignments[0].notification
    assert NotificationDao.get_notification(999) is None
    assert NotificationDao.get_assignment_notification(999) is None


def test_update_notification_leaves_other_assignment_unchanged(test_client, auth, assignments):
    target, other = assignments
    other_flags = other.notification.as_dict()

    response = test_client.patch(
        f"/api/v3/notifications/{target.notification.id}",
        json={"fail": False, "success": True},
        headers=auth.get_auth_header(),
    )

    assert response.status_code == 200
    db.session.refresh(target.notification)
    db.session.refresh(other.notification)
    assert target.notification.fail is False
    assert target.notification.success is True
    assert other.notification.as_dict() == other_flags
