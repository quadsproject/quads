from typing import List

from quads.server.dao.baseDao import BaseDao
from quads.server.models import Assignment, Vlan, db


class VlanDao(BaseDao):
    @classmethod
    def create_vlan(cls, gateway: str, ip_free: int, ip_range: str, netmask: str, vlan_id: int) -> Vlan:
        _vlan = Vlan(
            gateway=gateway,
            ip_free=ip_free,
            ip_range=ip_range,
            netmask=netmask,
            vlan_id=vlan_id,
        )
        db.session.add(_vlan)
        cls.safe_commit()
        return _vlan

    @staticmethod
    def get_vlan(vlan_id: int) -> Vlan:
        vlan = db.session.query(Vlan).filter(Vlan.vlan_id == vlan_id).first()
        return vlan

    @staticmethod
    def get_vlans() -> List[Vlan]:
        vlans = db.session.query(Vlan).order_by(Vlan.vlan_id).all()
        return vlans

    @staticmethod
    def get_free_vlans() -> List[Vlan]:
        vlans = (
            db.session.query(Vlan)
            .outerjoin(Assignment, (Vlan.id == Assignment.vlan_id) & (Assignment.active == True))
            .filter(Assignment.id == None)  # noqa: E711
            .order_by(Vlan.vlan_id)
            .all()
        )
        return vlans
