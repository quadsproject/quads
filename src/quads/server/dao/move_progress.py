from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import joinedload

from quads.server.dao.baseDao import BaseDao, EntryNotFound
from quads.server.dao.host import HostDao
from quads.server.models import Host, MoveProgress, db


class MoveProgressDao(BaseDao):
    @classmethod
    def create_move_progress(
        cls,
        host_id: int,
        source_cloud: str,
        target_cloud: str,
        schedule_id: int = None,
    ) -> MoveProgress:
        cls.cancel_stale(host_id)
        progress = MoveProgress(
            host_id=host_id,
            source_cloud=source_cloud,
            target_cloud=target_cloud,
            schedule_id=schedule_id,
            status="pending",
            started_at=datetime.now(),
        )
        db.session.add(progress)
        cls.safe_commit()
        return progress

    @classmethod
    def create_move_progress_batch(cls, records: list) -> dict:
        result = {}
        for record in records:
            hostname = record.get("hostname")
            host = HostDao.get_host(hostname)
            if not host:
                continue
            cls.cancel_stale(host.id)
            progress = MoveProgress(
                host_id=host.id,
                source_cloud=record.get("source_cloud", ""),
                target_cloud=record.get("target_cloud", ""),
                schedule_id=record.get("schedule_id"),
                status="pending",
                started_at=datetime.now(),
            )
            db.session.add(progress)
            result[hostname] = progress
        cls.safe_commit()
        return {hostname: p.id for hostname, p in result.items()}

    @classmethod
    def update_progress(cls, progress_id: int, **kwargs) -> MoveProgress:
        progress = db.session.query(MoveProgress).get(progress_id)
        if not progress:
            raise EntryNotFound
        for key, value in kwargs.items():
            if hasattr(progress, key):
                setattr(progress, key, value)
        status = kwargs.get("status")
        if status in ("completed", "failed"):
            progress.completed_at = datetime.now()
        cls.safe_commit()
        return progress

    @classmethod
    def get_active_by_hostname(cls, hostname: str) -> Optional[MoveProgress]:
        return (
            db.session.query(MoveProgress)
            .join(Host, MoveProgress.host_id == Host.id)
            .options(joinedload(MoveProgress.host).load_only(Host.name))
            .filter(Host.name == hostname)
            .filter(MoveProgress.status.notin_(["completed", "failed"]))
            .order_by(MoveProgress.created_at.desc())
            .first()
        )

    @classmethod
    def get_all_active(cls, cloud: str = None, status: str = None) -> List[MoveProgress]:
        query = (
            db.session.query(MoveProgress)
            .options(joinedload(MoveProgress.host).load_only(Host.name))
            .filter(MoveProgress.status.notin_(["completed", "failed"]))
        )
        if cloud:
            query = query.filter(MoveProgress.target_cloud == cloud)
        if status:
            query = query.filter(MoveProgress.status == status)
        return query.all()

    @classmethod
    def get_by_schedule(cls, schedule_id: int) -> List[MoveProgress]:
        return db.session.query(MoveProgress).filter(MoveProgress.schedule_id == schedule_id).all()

    @classmethod
    def cancel_stale(cls, host_id: int) -> None:
        stale = (
            db.session.query(MoveProgress)
            .filter(MoveProgress.host_id == host_id)
            .filter(MoveProgress.status.notin_(["completed", "failed"]))
            .all()
        )
        for record in stale:
            record.status = "failed"
            record.error_message = "Superseded by new move"
            record.completed_at = datetime.now()
        if stale:
            cls.safe_commit()
