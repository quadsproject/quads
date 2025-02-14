from typing import List

from quads.server.dao.baseDao import BaseDao, EntryNotFound
from quads.server.dao.host import HostDao
from quads.server.models import Processor, db


class ProcessorDao(BaseDao):
    @classmethod
    def create_processor(
        cls,
        hostname: str,
        handle: str,
        vendor: str,
        product: str,
        cores: int,
        threads: int,
        processor_type: str,
    ) -> Processor:
        _host_obj = HostDao.get_host(hostname)
        if not _host_obj:
            raise EntryNotFound
        _processor = Processor(
            handle=handle,
            vendor=vendor,
            product=product,
            cores=cores,
            threads=threads,
            host_id=_host_obj.id,
            processor_type=processor_type,
        )
        db.session.add(_processor)
        cls.safe_commit()
        return _processor

    @classmethod
    def delete_processor(cls, processor_id: int) -> None:  # pragma: no cover
        _processor = cls.get_processor(processor_id)
        if not _processor:
            raise EntryNotFound
        db.session.delete(_processor)
        return

    @staticmethod
    def get_processors() -> List[Processor]:  # pragma: no cover
        processors = db.session.query(Processor).all()
        return processors

    @staticmethod
    def get_processor(processor_id: int) -> Processor:
        processor = db.session.query(Processor).filter(Processor.id == processor_id).first()
        return processor

    @staticmethod
    def get_processor_for_host(host_id: int) -> List[Processor]:
        processors = db.session.query(Processor).filter(Processor.host_id == host_id).all()
        return processors
