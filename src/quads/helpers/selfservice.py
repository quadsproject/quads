from quads.config import Config
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao


def model_limit(model: str) -> int:
    """Maximum number of hosts of a model that may be self-scheduled at once."""
    pct = Config.get_ssm_model_limit(model)
    fleet = HostDao.count_hosts_by_model(model)
    return int(pct) * fleet // 100


def ssm_remaining_capacity(model: str, start, end, exclude_schedule_id: int = None) -> int:
    active = ScheduleDao.count_ss_schedules_by_model_overlap(
        model, start, end, exclude_schedule_id=exclude_schedule_id
    )
    return model_limit(model) - active
