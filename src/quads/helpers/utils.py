import calendar
import re
import logging

from datetime import timedelta, datetime

from quads.config import Config
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.schedule import ScheduleDao


def is_supported(_host_name):
    for host_type in Config.SUPPORTED:
        if host_type in _host_name:
            return True
    return False


def get_vlan(ass_obj, index, last_nic=False):
    if ass_obj and ass_obj.vlan and last_nic:
        return int(ass_obj.vlan.vlan_id)
    else:
        if ass_obj:
            _cloud_id = int(re.findall(r"\d+", ass_obj.cloud.name)[0])
            return calculate_vlan(_cloud_id, ass_obj.qinq, index)
        else:
            return calculate_vlan(1, 0, index)


def calculate_vlan(cloud_id, qinq, index):
    vlan_first = int(Config.sw_vlan_first) - 10
    cloud_offset = cloud_id * 10
    base_vlan = vlan_first + cloud_offset
    if qinq == 1:
        index = 0
    vlan = base_vlan + list(Config.OFFSETS.values())[index]
    return vlan


def date_span(start, end, delta=timedelta(days=1)):
    current = start
    while current < end:
        yield current
        current += delta


def month_delta_past(date, months):
    month = date.month - 1 - months
    year = date.year + month // 12
    month = month % 12 + 1
    _, last_day = calendar.monthrange(year, month)
    return datetime(year, month, last_day)


def last_day_month(date):
    next_month = date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)


def first_day_month(date):
    return date - timedelta(days=date.day - 1)


logger = logging.getLogger(__name__)


def check_assignment_provisioning_status(cloud_name):
    """
    Checks if all hosts in an assignment are built
    If so, marks the assignment as provisioned.
    """
    try:
        # Use DAOs directly to avoid circular imports with quads.server.app
        cloud = CloudDao.get_cloud(cloud_name)
        if not cloud:
            return

        assignment = AssignmentDao.get_active_cloud_assignment(cloud)

        if not assignment or assignment.provisioned:
            return

        # ScheduleDao typically takes kwargs for filtering
        current_schedules = ScheduleDao.get_current_schedules(cloud=cloud)

        if not current_schedules:
            return

        all_provisioned = True
        for schedule in current_schedules:
            if not schedule.host.build:
                all_provisioned = False
                break

        if all_provisioned:
            assignment.provisioned = True
            BaseDao.safe_commit()
            logger.info(f"Marked assignment for {assignment.cloud.name} as provisioned")

    except Exception as e:
        logger.error(f"Error checking assignment provisioning status for {cloud_name}: {e}")
