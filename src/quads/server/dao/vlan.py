from typing import List

from quads.server.dao.baseDao import BaseDao
from quads.server.models import Vlan, db


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
        # TODO:Union with assignments table on assignments.vlan_id=Vlan.vlan_id where assignments.active=True
        # to include a column with the assignment ID
        vlans = db.session.query(Vlan).all()
        return vlans
