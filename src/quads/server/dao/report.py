from sqlalchemy import func, extract

from quads.server.dao.baseDao import BaseDao
from quads.server.models import Assignment, Cloud, Schedule, db


class ReportDao(BaseDao):
    @staticmethod
    def get_detailed(start, end):
        query = (
            db.session.query(
                Assignment,
                Cloud.name.label("cloud_name"),
                func.count(Schedule.id).label("schedule_count"),
                func.min(Schedule.start).label("earliest_start"),
                func.ceil(extract("epoch", func.max(Schedule.end) - func.min(Schedule.start)) / 86400).label(
                    "total_span_days"
                ),
            )
            .outerjoin(Schedule, Schedule.assignment_id == Assignment.id)
            .outerjoin(Cloud, Assignment.cloud_id == Cloud.id)
        )

        if start:
            query = query.filter(Schedule.start >= start)
        if end:
            query = query.filter(Schedule.end <= end)

        query = query.group_by(Assignment.id, Cloud.name)
        report = query.all()

        return report
