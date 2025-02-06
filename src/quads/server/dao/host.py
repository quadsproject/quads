from typing import List, Optional

from sqlalchemy import Boolean, func

from quads.config import Config
from quads.server.dao.baseDao import (
    MAP_HOST_META,
    OPERATORS,
    BaseDao,
    EntryExisting,
    EntryNotFound,
    InvalidArgument,
)
from quads.server.dao.cloud import CloudDao
from quads.server.models import Cloud, Host, db


class HostDao(BaseDao):
    @classmethod
    def create_host(
        cls,
        name: str,
        model: str,
        host_type: str,
        default_cloud: str,
        can_self_schedule: bool = False,
        rack: str = None,
        uloc: str = None,
        blade: str = None,
    ) -> Host:
        _host_obj = cls.get_host(name)
        if _host_obj:
            raise EntryExisting
        if not default_cloud:
            default_cloud = Config["spare_pool_name"]
        _default_cloud_obj = CloudDao.get_cloud(default_cloud)
        if not _default_cloud_obj:
            raise EntryNotFound(f"Default cloud not found: {default_cloud}")
        _host = Host(
            name=name,
            model=model.upper(),
            host_type=host_type,
            can_self_schedule=can_self_schedule,
            default_cloud=_default_cloud_obj,
            cloud=_default_cloud_obj,
            rack=rack,
            uloc=uloc,
            blade=blade,
        )
        db.session.add(_host)
        cls.safe_commit()
        return _host

    @classmethod
    def update_host(cls, name: str, **kwargs) -> Host:
        """
        Updates a host in the database.

        :param self: Represent the instance of the class
        :param name: int: Identify the host to be updated
        :param model: str: Pass a string to the host model field
        :param host_type: str: Set the type of the host
        :param default_cloud: str: Update the host's default cloud
        :param cloud: int: Set the cloud value for a host

        :return: The updated host
        """
        host = cls.get_host(name)
        if not host:
            raise EntryNotFound

        for key, value in kwargs.items():
            if key in ["default_cloud", "cloud"]:
                cloud = CloudDao.get_cloud(value)
                if not cloud:
                    raise EntryNotFound
                setattr(host, key, cloud)
                continue

            if hasattr(host, key):
                setattr(host, key, value)
            else:
                raise InvalidArgument

        cls.safe_commit()

        return host

    @classmethod
    def remove_host(cls, name) -> None:
        _host_obj = cls.get_host(name)
        if not _host_obj:
            raise EntryNotFound
        db.session.delete(_host_obj)
        cls.safe_commit()
        return

    @staticmethod
    def get_host(hostname) -> Optional[Host]:
        host = db.session.query(Host).filter(Host.name == hostname).first()
        return host

    @staticmethod
    def get_hosts() -> List[Host]:
        hosts = db.session.query(Host).order_by(Host.name.asc()).all()
        return hosts

    @staticmethod
    def get_host_models():
        host_models = db.session.query(Host.model, func.count(Host.model)).group_by(Host.model).all()
        return host_models

    @staticmethod
    def filter_hosts_dict(data: dict) -> List[Host]:
        filter_tuples = []
        operator = "=="
        group_by = None
        for k, value in data.items():
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

            if fields[0].lower() == "group_by":
                first_field = value
                group_by = value
                k = value
            field = Host.__mapper__.attrs.get(first_field)
            if not field:
                raise InvalidArgument(f"{k} is not a valid field.")
            try:
                if type(field.columns[0].type) is Boolean:
                    value = value.lower() in ["true", "y", 1, "yes"]
            except AttributeError:
                if first_field in ["cloud", "default_cloud"]:
                    cloud = CloudDao.get_cloud(value)
                    if not cloud:
                        raise EntryNotFound(f"Cloud not found: {value}")
                    value = cloud
                if first_field.lower() in MAP_HOST_META.keys():
                    if len(fields) > 1:
                        field_name = f"{first_field.lower()}.{field_name.lower()}"

            if fields[0].lower() != "group_by":
                filter_tuples.append(
                    (
                        field_name,
                        operator,
                        value,
                    )
                )
        _hosts = HostDao.create_query_select(Host, filters=filter_tuples, group_by=group_by, order_by=Host.name.asc())
        return _hosts

    @staticmethod
    def filter_hosts(  # pragma: no cover
        model: str = None,
        host_type: str = None,
        build: bool = None,
        validated: bool = None,
        switch_config_applied: bool = None,
        broken: bool = None,
        retired: bool = None,
        cloud: Cloud = None,
        default_cloud: Cloud = None,
    ) -> List[Host]:
        # TODO: Add children filters for interfaces, disk, memory and processor
        query = db.session.query(Host)
        if model:
            query = query.filter(Host.model == model)
        if host_type:
            query = query.filter(Host.host_type == host_type)
        if build is not None:
            query = query.filter(Host.build == build)
        if validated is not None:
            query = query.filter(Host.validated == validated)
        if switch_config_applied is not None:
            query = query.filter(Host.switch_config_applied == switch_config_applied)
        if broken is not None:
            query = query.filter(Host.broken == broken)
        if retired is not None:
            query = query.filter(Host.retired == retired)
        if cloud:
            query = query.filter(Host.cloud == cloud)
        if default_cloud:
            query = query.filter(Host.default_cloud == default_cloud)
        hosts = query.all()
        return hosts
