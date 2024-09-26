from typing import List

from quads.server.dao.baseDao import BaseDao, EntryNotFound
from quads.server.dao.host import HostDao
from quads.server.models import Disk, db


class DiskDao(BaseDao):
    @classmethod
    def create_disk(
        cls,
        hostname: str,
        disk_type: str,
        size_gb: int,
        count: int,
    ) -> Disk:
        _host_obj = HostDao.get_host(hostname)
        if not _host_obj:  # pragma: no cover
            raise EntryNotFound
        _disk = Disk(
            disk_type=disk_type,
            size_gb=size_gb,
            count=count,
            host_id=_host_obj.id,
        )
        db.session.add(_disk)
        cls.safe_commit()
        return _disk

    @staticmethod
    def get_disks() -> List[Disk]:  # pragma: no cover
        disks = db.session.query(Disk).all()
        return disks

    @staticmethod
    def get_disk(disk_id: int) -> Disk:
        disk = db.session.query(Disk).filter(Disk.id == disk_id).first()
        return disk

    @classmethod
    def delete_disk(cls, disk_id) -> None:  # pragma: no cover
        _disk_obj = cls.get_disk(disk_id)
        if not _disk_obj:
            raise EntryNotFound
        db.session.delete(_disk_obj)
        cls.safe_commit()
        return
