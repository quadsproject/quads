from typing import Optional

from quads.config import Config
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao


def model_limit(model: str) -> int:
    """Maximum number of hosts of a model that may be self-scheduled at once."""
    pct = Config.get_ssm_model_limit(model)
    fleet = HostDao.count_hosts_by_model(model)
    limit = int(pct) * fleet // 100
    if pct > 0 and fleet > 0:
        # Floor honors the advertised percentage exactly for any fleet that
        # yields at least one host; a sub-host fleet still gets one slot so a
        # non-zero percentage never silently disables the model. pct=0 stays 0.
        limit = max(1, limit)
    return limit


def ssm_remaining_capacity(model: str, start, end, exclude_schedule_id: Optional[int] = None) -> int:
    # ponytail: check-then-act, not serialized across clouds (same ceiling as the
    # existing ssm_host_limit check). Upgrade path: pg_advisory_xact_lock(
    # hashtext(model)) (or a per-model for_update) if a hard "at most N% at any
    # time" bound under concurrency is ever required.
    active = ScheduleDao.count_ss_schedules_by_model_overlap(
        model, start, end, exclude_schedule_id=exclude_schedule_id
    )
    return model_limit(model) - active
