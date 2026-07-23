import calendar
import re

from datetime import timedelta, datetime

from quads.config import Config


def is_supermicro(_host_name):
    host_lower = _host_name.lower()
    return any(host_type.lower() in host_lower for host_type in Config.SUPERMICRO)


def is_libvirt(host_obj) -> bool:
    return host_obj.model.upper() == "LIBVIRT"


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


def time_remaining(end_date, start_date=None):
    if start_date is None:
        start_date = datetime.now()
    td = end_date - start_date
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return 0, 0
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    return days, hours
