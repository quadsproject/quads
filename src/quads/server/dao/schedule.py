from datetime import datetime, timedelta
from typing import List, Type, Dict, Any, Optional

from sqlalchemy import Boolean, and_, func, text, case, distinct
from sqlalchemy.dialects.postgresql import array_agg

from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import (
    OPERATORS,
    BaseDao,
    EntryNotFound,
    InvalidArgument,
    SQLError,
)
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.models import Assignment, Cloud, Host, Schedule, db


class ScheduleDao(BaseDao):
    @classmethod
    def create_schedule(cls, start: datetime, end: datetime, assignment: Assignment, host: Host) -> Schedule:
        _schedule_obj = Schedule(start=start, end=end, assignment=assignment, host=host)
        db.session.add(_schedule_obj)
        cls.safe_commit()
        return _schedule_obj

    @classmethod
    def update_schedule(cls, sched_id: int, **kwargs) -> Schedule:
        """
        Updates a host in the database.

        :param sched_id: str: Identify the schedule to be updated to
        :param hostname: str: Identify the host to be updated to
        :param start: datetime: Pass a string with the schedule start date
        :param end: datetime: Pass a string with the schedule end date
        :param build_start: datetime: Pass a string with the schedule start build date
        :param build_end: datetime: Pass a string with the schedule end build date

        :return: The updated schedule
        """
        schedule = cls.get_schedule(sched_id)
        if not schedule:  # pragma: no cover
            raise EntryNotFound

        for key, value in kwargs.items():
            if key == "hostname":
                host = HostDao.get_host(value)
                if not host:
                    raise EntryNotFound
                setattr(schedule, key, host)
                continue

            if hasattr(schedule, key):
                setattr(schedule, key, value)
            else:
                raise InvalidArgument(f"{key} is not a valid field.")

        result = cls.safe_commit()

        if not result:  # pragma: no cover
            raise SQLError("Failed to update schedule")

        return schedule

    @classmethod
    def remove_schedule(cls, schedule_id: int) -> None:
        _schedule_obj = cls.get_schedule(schedule_id)
        if not _schedule_obj:  # pragma: no cover
            raise EntryNotFound
        db.session.delete(_schedule_obj)
        cls.safe_commit()
        return

    @staticmethod
    def get_schedules() -> List[Schedule]:
        schedules = db.session.query(Schedule).order_by(Schedule.id).all()
        return schedules

    @staticmethod
    def get_schedule(schedule_id: int) -> Schedule:
        schedule = db.session.query(Schedule).filter(Schedule.id == schedule_id).first()
        return schedule

    @staticmethod
    def get_future_schedules(host: Host = None, cloud: Cloud = None) -> List[Schedule]:
        now = datetime.now()
        query = db.session.query(Schedule).filter(Schedule.end >= now)
        if host:
            query = query.filter(Schedule.host == host)
        if cloud:
            assignments = AssignmentDao.get_all_cloud_assignments(cloud)
            query = query.join(Assignment).filter(Assignment.id.in_((ass.id for ass in assignments)))
        future_schedules = query.all()
        return future_schedules

    @staticmethod
    def filter_schedule_dict(data: dict) -> List[Schedule]:
        filter_tuples = []
        date_fields = ["start", "end", "build_start", "build_end"]
        group_by = None
        for k, value in data.items():
            operator = "=="
            fields = k.split(".")
            if len(fields) > 2:
                raise InvalidArgument(f"Too many arguments: {fields}")

            first_field = fields[0]
            field_name = fields[-1]
            if "__" in k:
                op = f"__{k.split('__')[-1]}"
                operator = OPERATORS.get(op)
                if not operator:
                    raise InvalidArgument(f"{op} is not a valid operator.")
                if first_field == field_name:
                    first_field = field_name[: field_name.index(op)]
                field_name = field_name[: field_name.index(op)]

            if value and isinstance(value, str) and value.lower() == "none":
                value = None

            if fields[0].lower() == "group_by":
                first_field = value
                group_by = value
                k = value
            field = Schedule.__mapper__.attrs.get(first_field)
            if not field:
                raise InvalidArgument(f"{k} is not a valid field.")
            try:
                if type(field.columns[0].type) is Boolean:
                    value = value.lower() in ["true", "y", 1, "yes"]
            except AttributeError:
                if first_field.lower() == "host":
                    host = HostDao.get_host(value)
                    if not host:
                        raise EntryNotFound(f"Host not found: {value}")
                    value = host
                    field_name = first_field

            if first_field in date_fields:
                try:
                    if value and isinstance(value, str):
                        value = datetime.strptime(value, "%Y-%m-%dT%H:%M")
                except ValueError:
                    raise InvalidArgument(f"Invalid date format for {first_field}: {value}")

            if fields[0].lower() != "group_by":
                filter_tuples.append(
                    (
                        field_name,
                        operator,
                        value,
                    )
                )
        try:
            _schedules = ScheduleDao.create_query_select(
                Schedule, filters=filter_tuples, group_by=group_by, order_by=Schedule.id.asc()
            )
        except Exception as e:
            raise InvalidArgument(str(e))
        return _schedules

    @staticmethod
    def filter_schedules(
        start: datetime = None,
        end: datetime = None,
        host: str = None,
        cloud: str = None,
    ) -> List[Type[Schedule]]:
        query = db.session.query(Schedule)
        if start:
            if isinstance(start, str):
                try:
                    start_date = datetime.strptime(start, "%Y-%m-%dT%H:%M")
                    start = start_date
                except ValueError:
                    raise InvalidArgument(
                        "start argument must be a datetime object or a correct datetime format string"
                    )
            elif not isinstance(start, datetime):
                raise InvalidArgument("start argument must be a datetime object")
            query = query.filter(Schedule.start >= start)
        if end:
            if isinstance(end, str):
                try:
                    end_date = datetime.strptime(end, "%Y-%m-%dT%H:%M")
                    end = end_date
                except ValueError:
                    raise InvalidArgument("end argument must be a datetime object or a correct datetime format string")
            elif not isinstance(end, datetime):
                raise InvalidArgument("end argument must be a datetime object")
            query = query.filter(Schedule.end <= end)
        if host:
            if not isinstance(host, str):
                raise InvalidArgument("host argument must be a str object")
            query = query.filter(Schedule.host.has(name=host))
        if cloud:
            if not isinstance(cloud, str):
                raise InvalidArgument("cloud argument must be a str object")
            cloud_obj = CloudDao.get_cloud(cloud)
            query = query.filter(Schedule.assignment.has(cloud_id=cloud_obj.id))
        filter_schedules = query.all()
        return filter_schedules

    @staticmethod
    def get_current_schedule(date: datetime = None, host: Host = None, cloud: Cloud = None) -> List[Type[Schedule]]:
        query = db.session.query(Schedule)
        if cloud:
            query = query.join(Assignment).filter(Assignment.cloud == cloud)
        if not date:
            date = datetime.now()
        query = query.filter(and_(Schedule.start <= date, Schedule.end >= date))

        if host:
            query = query.filter(Schedule.host == host)

        current_schedule = query.all()
        return current_schedule

    @staticmethod
    def get_hosts_range_schedules(start: datetime = None, end: datetime = None):
        now = datetime.now()
        _start = start if start else now
        _end = end if end else now
        hosts_schedules = (
            db.session.query(
                Host.name,
                func.coalesce(
                    array_agg(
                        func.json_build_object(
                            "id",
                            Schedule.id,
                            "assignment_id",
                            Schedule.assignment_id,
                            "start",
                            Schedule.start,
                            "end",
                            Schedule.end,
                            "cloud",
                            Cloud.name,
                            "description",
                            Assignment.description,
                            "owner",
                            Assignment.owner,
                            "ticket",
                            Assignment.ticket,
                        )
                    ),
                    [],
                ),
            )
            .outerjoin(Schedule, Host.id == Schedule.host_id)
            .outerjoin(Assignment, Schedule.assignment_id == Assignment.id)
            .outerjoin(Cloud, Assignment.cloud_id == Cloud.id)
            .filter(Schedule.start <= _end, Schedule.end >= _start)
            .group_by(Host.name)
            .all()
        )
        return hosts_schedules

    @staticmethod
    def is_host_available(hostname, start, end, exclude=None) -> bool:
        _host = HostDao.get_host(hostname)

        if not _host:
            return False
        if _host.broken or _host.retired:
            return False
        query = db.session.query(Schedule)
        query = query.filter(Schedule.host == _host)
        if exclude:
            query = query.filter(Schedule.id != exclude)
        results = query.all()
        for result in results:
            if result.start <= start < result.end:
                return False
            if result.start < end <= result.end:
                return False
            if start < result.start and end > result.end:
                return False

        return True

    @staticmethod
    def get_daily_allocation_data(
        start: datetime, end: datetime, host_names: Optional[List[str]] = None, offset: int = 0, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get daily allocation data optimized for calendar visualization.

        Uses PostgreSQL generate_series to create all days in range and joins
        with schedules to get allocation status for each day.

        Args:
            start: Start date of the range
            end: End date of the range
            host_names: Optional list of specific hosts to query
            offset: Starting offset for pagination
            limit: Maximum number of hosts to return

        Returns:
            List of dictionaries with daily allocation data per host
        """
        # Build host filter subquery
        host_filter = ""
        if host_names:
            host_list = "','".join(host_names)
            host_filter = f"AND h.name IN ('{host_list}')"

        # PostgreSQL query using generate_series for date range
        query = text(
            f"""
            WITH date_series AS (
                SELECT generate_series(
                    :start_date::date,
                    :end_date::date,
                    '1 day'::interval
                )::date as day
            ),
            host_batch AS (
                SELECT h.id, h.name
                FROM hosts h
                WHERE h.retired = false AND h.broken = false
                {host_filter}
                ORDER BY h.name
                LIMIT :limit OFFSET :offset
            ),
            daily_allocations AS (
                SELECT
                    hb.name as hostname,
                    ds.day,
                    s.id as schedule_id,
                    s.assignment_id,
                    c.name as cloud,
                    a.description,
                    a.owner,
                    a.ticket,
                    EXTRACT(day FROM ds.day) as day_num
                FROM host_batch hb
                CROSS JOIN date_series ds
                LEFT JOIN schedules s ON hb.id = s.host_id
                    AND ds.day BETWEEN s.start::date AND s.end::date
                LEFT JOIN assignments a ON s.assignment_id = a.id
                LEFT JOIN clouds c ON a.cloud_id = c.id
            )
            SELECT
                hostname,
                json_agg(
                    json_build_object(
                        'day', day_num,
                        'allocated', CASE WHEN schedule_id IS NOT NULL THEN true ELSE false END,
                        'assignment_id', assignment_id,
                        'cloud', COALESCE(cloud, 'cloud01'),
                        'description', description,
                        'owner', owner,
                        'ticket', ticket
                    ) ORDER BY day_num
                ) as days
            FROM daily_allocations
            GROUP BY hostname
            ORDER BY hostname
        """
        )

        result = db.session.execute(
            query, {"start_date": start.date(), "end_date": end.date(), "limit": limit, "offset": offset}
        )

        return [{"hostname": row[0], "days": row[1]} for row in result]

    @staticmethod
    def get_allocation_metrics(start: datetime, end: datetime) -> Dict[str, Any]:
        """
        Get aggregated allocation metrics for fast metadata queries.

        Args:
            start: Start date of the range
            end: End date of the range

        Returns:
            Dictionary with allocation metrics
        """
        # Count total active hosts
        total_hosts_query = db.session.query(func.count(Host.id)).filter(Host.retired == False, Host.broken == False)
        total_hosts = total_hosts_query.scalar()

        # Get current allocations (for daily utilization)
        now = datetime.now()
        current_allocations_query = db.session.query(func.count(distinct(Schedule.host_id))).filter(
            Schedule.start <= now, Schedule.end >= now
        )
        current_allocations = current_allocations_query.scalar() or 0

        # Get monthly allocation statistics
        monthly_stats_query = db.session.query(
            func.count(distinct(Schedule.host_id)).label("allocated_hosts"),
            func.count(Schedule.id).label("total_schedules"),
            func.avg(func.extract("epoch", Schedule.end - Schedule.start) / 86400).label("avg_allocation_days"),
        ).filter(Schedule.start <= end, Schedule.end >= start)

        monthly_stats = monthly_stats_query.first()
        allocated_hosts = monthly_stats.allocated_hosts or 0
        total_schedules = monthly_stats.total_schedules or 0

        # Calculate utilization percentages
        daily_utilization = (current_allocations * 100) // total_hosts if total_hosts > 0 else 0
        monthly_utilization = (allocated_hosts * 100) // total_hosts if total_hosts > 0 else 0

        return {
            "total_hosts": total_hosts,
            "allocated_hosts": allocated_hosts,
            "current_allocations": current_allocations,
            "total_schedules": total_schedules,
            "daily_utilization": daily_utilization,
            "monthly_utilization": monthly_utilization,
            "avg_allocation_days": float(monthly_stats.avg_allocation_days or 0),
        }

    @staticmethod
    def get_hosts_with_allocation_priority(
        start: datetime, end: datetime, priority: str = "mixed", offset: int = 0, limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get hosts ordered by allocation priority for progressive loading.

        Args:
            start: Start date of the range
            end: End date of the range
            priority: 'allocated' (hosts with schedules first),
                     'available' (unallocated first), or 'mixed' (alphabetical)
            offset: Starting offset for pagination
            limit: Maximum number of hosts to return

        Returns:
            Dictionary with host batch info and allocation counts
        """
        # Base query for active hosts with schedule counts
        base_query = (
            db.session.query(
                Host.name,
                func.count(Schedule.id).label("schedule_count"),
                func.coalesce(func.bool_or(and_(Schedule.start <= end, Schedule.end >= start)), False).label(
                    "has_allocations"
                ),
            )
            .outerjoin(Schedule, and_(Host.id == Schedule.host_id, Schedule.start <= end, Schedule.end >= start))
            .filter(Host.retired == False, Host.broken == False)
            .group_by(Host.id, Host.name)
        )

        # Apply ordering based on priority
        if priority == "allocated":
            base_query = base_query.order_by(func.count(Schedule.id).desc(), Host.name)
        elif priority == "available":
            base_query = base_query.order_by(func.count(Schedule.id).asc(), Host.name)
        else:  # mixed - alphabetical
            base_query = base_query.order_by(Host.name)

        # Get total count for pagination info
        total_count_query = db.session.query(func.count(Host.id)).filter(Host.retired == False, Host.broken == False)
        total_count = total_count_query.scalar()

        # Apply pagination
        hosts_batch = base_query.offset(offset).limit(limit).all()

        return {
            "hosts": [
                {"hostname": host.name, "schedule_count": host.schedule_count, "has_allocations": host.has_allocations}
                for host in hosts_batch
            ],
            "batch_info": {
                "offset": offset,
                "limit": limit,
                "returned": len(hosts_batch),
                "total_hosts": total_count,
                "has_more": (offset + limit) < total_count,
                "next_offset": offset + limit if (offset + limit) < total_count else None,
                "priority": priority,
            },
        }

    @staticmethod
    def get_hosts_schedule_summary(
        start: datetime, end: datetime, host_names: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get lightweight schedule summary for hosts without daily breakdown.

        Optimized for initial table structure creation.

        Args:
            start: Start date of the range
            end: End date of the range
            host_names: Optional list of specific hosts to query

        Returns:
            Dictionary mapping hostnames to schedule summaries
        """
        query = (
            db.session.query(
                Host.name,
                func.coalesce(
                    array_agg(
                        func.json_build_object(
                            "assignment_id",
                            Schedule.assignment_id,
                            "start",
                            Schedule.start,
                            "end",
                            Schedule.end,
                            "cloud",
                            Cloud.name,
                            "description",
                            Assignment.description,
                            "owner",
                            Assignment.owner,
                            "ticket",
                            Assignment.ticket,
                        )
                    ),
                    text("ARRAY[]::json[]"),
                ).label("schedules"),
            )
            .outerjoin(Schedule, and_(Host.id == Schedule.host_id, Schedule.start <= end, Schedule.end >= start))
            .outerjoin(Assignment, Schedule.assignment_id == Assignment.id)
            .outerjoin(Cloud, Assignment.cloud_id == Cloud.id)
            .filter(Host.retired == False, Host.broken == False)
        )

        # Apply host name filter if provided
        if host_names:
            query = query.filter(Host.name.in_(host_names))

        query = query.group_by(Host.name).order_by(Host.name)

        result = query.all()
        return {row.name: row.schedules for row in result}
