import os
from datetime import datetime, timedelta
from typing import Any

from flask import current_app
from flask_migrate import Migrate
from flask_security import UserMixin, RoleMixin
from flask_sqlalchemy import SQLAlchemy
from jwt import encode, decode, ExpiredSignatureError, InvalidTokenError
from sqlalchemy import (
    Column,
    Enum,
    Integer,
    String,
    Boolean,
    ForeignKey,
    PickleType,
    DateTime,
    func,
    create_engine,
    inspect,
    MetaData,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import relationship, backref

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)
db = SQLAlchemy()
migrate = Migrate()
SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI", "postgresql://postgres:postgres@quads_db:5432/quads")
Engine = create_engine(
    SQLALCHEMY_DATABASE_URI,
    pool_size=10,
    max_overflow=2,
    pool_recycle=300,
    pool_pre_ping=True,
    pool_use_lifo=True,
)
Base.query = db.session.query_property()


def engine_from_config(config):
    global Engine
    Engine = create_engine(
        config["SQLALCHEMY_DATABASE_URI"],
        pool_size=10,
        max_overflow=2,
        pool_recycle=300,
        pool_pre_ping=True,
        pool_use_lifo=True,
    )
    return Engine


class TimestampMixin:
    @declared_attr.cascading
    def created_at(self):
        return Column(DateTime, default=func.now())


class Serialize:
    def as_dict(self):
        obj_attrs = inspect(self).mapper.attrs
        result = {}
        for attr in obj_attrs:
            if attr.key == "cloud":
                cloud = getattr(self, attr.key)
                if cloud:
                    result["cloud"] = cloud.as_dict()
            if attr.key == "host":
                result["host"] = getattr(self, attr.key).as_dict()
            if attr.key == "default_cloud":
                default_cloud = getattr(self, attr.key)
                if default_cloud:
                    result["default_cloud"] = default_cloud.as_dict()
            if attr.key == "vlan":
                vlan = getattr(self, attr.key)
                if vlan:
                    result["vlan"] = vlan.as_dict()
            if attr.key == "assignment":
                assignment = getattr(self, attr.key)
                if assignment:
                    result["assignment"] = assignment.as_dict()
            if attr.key == "notification":
                notification = getattr(self, attr.key)
                notification.assignment = None
                result["notification"] = notification.as_dict()
            if attr.key == "disks":
                disk_list = []
                disks = getattr(self, attr.key, [])
                if disks:
                    for disk in disks:
                        disk_list.append(disk.as_dict())
                    result["disks"] = disk_list
            if attr.key == "memory":
                memory_list = []
                memory_val = getattr(self, attr.key, [])
                if memory_val:
                    for memory in memory_val:
                        memory_list.append(memory.as_dict())
                    result["memory"] = memory_list
            if attr.key == "interfaces":
                interface_list = []
                interfaces = getattr(self, attr.key, [])
                if interfaces:
                    for interface in interfaces:
                        interface_list.append(interface.as_dict())
                    result["interfaces"] = interface_list
            if attr.key == "processors":
                processor_list = []
                processors = getattr(self, attr.key, [])
                if processors:
                    for processor in processors:
                        processor_list.append(processor.as_dict())
                    result["processors"] = processor_list
        all_else = {
            c.key: getattr(self, c.key)
            for c in obj_attrs
            if c.key
            not in [
                "cloud",
                "host",
                "default_cloud",
                "disks",
                "interfaces",
                "memory",
                "processors",
                "notification",
                "notifications",
                "assignment",
                "vlan",
            ]
        }
        return {**result, **all_else}

    def from_dict(self, data):
        obj_attrs = inspect(self).mapper.attrs
        for attr in obj_attrs:
            if attr.key in ["cloud", "default_cloud"]:
                if isinstance(data, dict):
                    value = data.get(attr.key)
                else:
                    value = getattr(data, attr.key)
                if value:
                    cloud = Cloud().from_dict(value)
                    setattr(self, attr.key, cloud)
                continue
            if attr.key == "host":
                value = data.get(attr.key)
                if value:
                    host = Host().from_dict(value)
                    setattr(self, attr.key, host)
                continue
            if attr.key == "vlan":
                if isinstance(data, dict):
                    value = data.get(attr.key)
                else:
                    value = getattr(data, attr.key)
                if value:
                    vlan = Vlan().from_dict(value)
                    setattr(self, attr.key, vlan)
                continue
            if attr.key == "assignment":
                if isinstance(data, dict):
                    value = data.get(attr.key)
                else:
                    value = getattr(data, attr.key)
                if value:
                    assignment = Assignment().from_dict(value)
                    setattr(self, attr.key, assignment)
                continue
            if attr.key == "notification":
                if isinstance(data, dict):
                    value = data.get(attr.key)
                else:
                    value = getattr(data, attr.key)
                if value:
                    notification = Notification().from_dict(value)
                    setattr(self, attr.key, notification)
                continue
            if attr.key == "disks":
                disk_list = []
                disks = data.get(attr.key, [])
                if disks:
                    for disk in disks:
                        disk_obj = Disk().from_dict(disk)
                        disk_list.append(disk_obj)
                    setattr(self, attr.key, disk_list)
                continue
            if attr.key == "memory":
                memory_list = []
                memory_val = data.get(attr.key, [])
                if memory_val:
                    for memory in memory_val:
                        memory_obj = Memory().from_dict(memory)
                        memory_list.append(memory_obj)
                    setattr(self, attr.key, memory_list)
                continue
            if attr.key == "interfaces":
                interface_list = []
                interfaces = data.get(attr.key, [])
                if interfaces:
                    for interface in interfaces:
                        interface_obj = Interface().from_dict(interface)
                        interface_list.append(interface_obj)
                    setattr(self, attr.key, interface_list)
                continue
            if attr.key == "processors":
                processor_list = []
                processors = data.get(attr.key, [])
                if processors:
                    for processor in processors:
                        processor_obj = Processor().from_dict(processor)
                        processor_list.append(processor_obj)
                    setattr(self, attr.key, processor_list)
                continue
            if isinstance(data, dict):
                value = data.get(attr.key)
            else:
                value = getattr(data, attr.key)
            if value is not None:
                if type(attr.columns[0].type) is DateTime:
                    if not isinstance(value, datetime):
                        value = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT")
                setattr(self, attr.key, value)
        return self


class RolesUsers(Base):
    __tablename__ = "roles_users"
    id = Column(Integer(), primary_key=True)
    user_id = Column("user_id", Integer(), ForeignKey("users.id"))
    role_id = Column("role_id", Integer(), ForeignKey("roles.id"))


class Role(Base, RoleMixin):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True)
    description = Column(String(255))


class User(Base, UserMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    fs_uniquifier = Column(String(256), unique=True, nullable=False)
    email = Column(String(256), unique=True, nullable=False)
    _password = Column("password", String(256), nullable=False)
    active = Column(Boolean(), default=True)
    confirmed_at = Column(DateTime())
    # many-to-many parent
    roles = relationship(
        "Role",
        secondary="roles_users",
        backref=backref("users", lazy="dynamic"),
    )

    def get_id(self):
        """Return the email address to satisfy Flask-Login's requirements."""
        return self.email

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self._password = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self._password, password)

    @staticmethod
    def encode_auth_token(user_email, user_role=None):
        try:
            payload = {
                "exp": datetime.utcnow() + timedelta(days=0, seconds=15600),
                "iat": datetime.utcnow(),
                "sub": user_email,
            }
            if user_role:
                payload["role"] = user_role
            return encode(payload, current_app.config.get("SECRET_KEY"), algorithm="HS256")
        except Exception as e:
            return e

    @staticmethod
    def decode_auth_token(auth_token):
        try:
            payload = decode(auth_token, current_app.config.get("SECRET_KEY"), algorithms="HS256")
            is_token_blacklisted = TokenBlackList.check_blacklist(auth_token)
            if is_token_blacklisted:
                return "Token blacklisted. Please log in again."
            else:
                return payload["sub"]
        except ExpiredSignatureError:
            return "Signature expired. Please log in again."
        except InvalidTokenError:
            return "Invalid token. Please log in again."


class TokenBlackList(Base):
    __tablename__ = "tokens_blacklist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False)
    blacklisted_on = Column(DateTime, nullable=False)

    def __init__(self, token, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.token = token
        self.blacklisted_on = datetime.now()

    def __repr__(self):
        return "<id: token: {}".format(self.token)

    @staticmethod
    def check_blacklist(auth_token):
        # check whether auth token has been blacklisted
        res = TokenBlackList.query.filter_by(token=str(auth_token)).first()
        if res:
            return True
        else:
            return False


class Vlan(Serialize, Base):
    __tablename__ = "vlans"
    id = Column(Integer, primary_key=True)
    gateway = Column(String)
    ip_free = Column(Integer)
    ip_range = Column(String)
    netmask = Column(String)
    vlan_id = Column(Integer)

    def __repr__(self):
        return "<Vlan(vlan_id='{}', ip_free='{}', ip_range={}, netmask={}, gateway={})>".format(
            self.vlan_id, self.ip_free, self.ip_range, self.netmask, self.gateway
        )


class Notification(Serialize, Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    fail = Column(Boolean, default=False)
    success = Column(Boolean, default=False)
    initial = Column(Boolean, default=False)
    pre_initial = Column(Boolean, default=False)
    pre = Column(Boolean, default=False)
    one_day = Column(Boolean, default=False)
    three_days = Column(Boolean, default=False)
    five_days = Column(Boolean, default=False)
    seven_days = Column(Boolean, default=False)

    # one-to-one child
    assignment_id = Column(Integer, ForeignKey("assignments.id"))

    def __repr__(self):
        return (
            "<Notification(id='{}', fail='{}', success='{}', initial='{}', pre_initial='{}', "
            "pre='{}', one_day='{}', three_days='{}', five_days='{}', seven_days='{}', assignment_id='{}')>".format(
                self.id,
                self.fail,
                self.success,
                self.initial,
                self.pre_initial,
                self.pre,
                self.one_day,
                self.three_days,
                self.five_days,
                self.seven_days,
                self.assignment_id,
            )
        )


class Cloud(Serialize, Base):
    __tablename__ = "clouds"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    last_redefined = Column(DateTime, default=func.now())

    def __repr__(self):
        return "<Cloud(id='{}', name='{}', last_redefined='{}')>".format(self.id, self.name, self.last_redefined)


class Assignment(Serialize, TimestampMixin, Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    active = Column(Boolean, default=True)
    provisioned = Column(Boolean, default=False)
    validated = Column(Boolean, default=False)
    description = Column(String)
    owner = Column(String)
    ticket = Column(String)
    qinq = Column(Integer)
    wipe = Column(Boolean, default=False)
    ccuser = Column(MutableList.as_mutable(PickleType), default=[])
    is_self_schedule = Column(Boolean, default=False)
    ostype = Column(String)
    boot_order = Column(String)

    # many-to-one parent
    cloud_id = Column(Integer, ForeignKey("clouds.id", ondelete="SET NULL"))
    cloud = relationship("Cloud", foreign_keys=[cloud_id])

    # one-to-one parent
    notification = relationship("Notification", cascade="all, delete-orphan", uselist=False)

    # one-to-one parent
    vlan_id = Column(Integer, ForeignKey("vlans.id"))
    vlan = relationship("Vlan")

    def __repr__(self):
        return (
            "<Assignment(id='{}', active='{}', provisioned='{}', validated='{}', description='{}', "
            "owner='{}', ticket='{}', qinq='{}', wipe='{}', ccuser='{}', is_self_schedule='{}', cloud='{}', vlan='{}', "
            "ostype='{}', boot_order='{}')>".format(
                self.id,
                self.active,
                self.provisioned,
                self.validated,
                self.description,
                self.owner,
                self.ticket,
                self.qinq,
                self.wipe,
                self.ccuser,
                self.is_self_schedule,
                self.cloud,
                self.vlan,
                self.ostype,
                self.boot_order,
            )
        )


class Disk(Serialize, Base):
    __tablename__ = "disks"
    id = Column(Integer, primary_key=True)
    disk_type = Column(String)
    size_gb = Column(Integer)
    count = Column(Integer)

    host_id = Column(Integer, ForeignKey("hosts.id"))

    def __repr__(self):
        return "<Disk(id='{}', disk_type='{}', size_gb='{}', count='{}')>".format(
            self.id, self.disk_type, self.size_gb, self.count
        )


class Memory(Serialize, Base):
    __tablename__ = "memory"
    id = Column(Integer, primary_key=True)
    handle = Column(String)
    size_gb = Column(Integer)

    host_id = Column(Integer, ForeignKey("hosts.id"))

    def __repr__(self):
        return "<Memory(id='{}', handle='{}', size_gb='{}')>".format(self.id, self.handle, self.size_gb)


class Processor(Serialize, Base):
    __tablename__ = "processors"
    id = Column(Integer, primary_key=True)
    handle = Column(String)
    vendor = Column(String)
    product = Column(String)
    cores = Column(Integer)
    threads = Column(Integer)
    processor_type = Column(Enum("CPU", "GPU", name="processor_type_enum"))

    host_id = Column(Integer, ForeignKey("hosts.id"))

    def __repr__(self):
        return "<Processor(id='{}', handle='{}', vendor='{}', product='{}', cores='{}', threads='{}')>".format(
            self.id, self.handle, self.vendor, self.product, self.cores, self.threads
        )


class Interface(Serialize, Base):
    __tablename__ = "interfaces"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    bios_id = Column(String)
    mac_address = Column(String)
    switch_ip = Column(String)
    switch_port = Column(String)
    speed = Column(Integer)
    vendor = Column(String)
    pxe_boot = Column(Boolean, default=False)
    maintenance = Column(Boolean, default=False)

    host_id = Column(Integer, ForeignKey("hosts.id"))

    def __repr__(self):
        return (
            "<Interface(id='{}', name='{}', biod_id='{}', mac_address='{}', switch_ip='{}', "
            "switch_port='{}', speed='{}', vendor='{}', pxe_boot='{}', maintenance='{}')>".format(
                self.id,
                self.name,
                self.bios_id,
                self.mac_address,
                self.switch_ip,
                self.switch_port,
                self.speed,
                self.vendor,
                self.pxe_boot,
                self.maintenance,
            )
        )


class Host(Serialize, TimestampMixin, Base):
    __tablename__ = "hosts"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    model = Column(String)
    host_type = Column(String)
    build = Column(Boolean, default=False)
    validated = Column(Boolean, default=False)
    switch_config_applied = Column(Boolean, default=False)
    broken = Column(Boolean, default=False)
    retired = Column(Boolean, default=False)
    last_build = Column(DateTime)
    can_self_schedule = Column(Boolean, default=True)
    rack = Column(String)
    uloc = Column(String)
    blade = Column(String)
    bootmode = Column(Enum("Bios", "Uefi", name="bootmode_enum"), default=None, nullable=True)

    # many-to-one
    cloud_id = Column(Integer, ForeignKey("clouds.id"))
    cloud = relationship("Cloud", foreign_keys=[cloud_id])

    # many-to-one
    default_cloud_id = Column(Integer, ForeignKey("clouds.id"))
    default_cloud = relationship("Cloud", foreign_keys=[default_cloud_id])

    # one-to-many parent
    interfaces = relationship("Interface", cascade="all, delete-orphan", lazy="select")

    # one-to-many parent
    disks = relationship("Disk", cascade="all, delete-orphan", lazy="select")

    # one-to-many parent
    memory = relationship("Memory", cascade="all, delete-orphan", lazy="select")

    # one-to-many parent
    processors = relationship("Processor", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return (
            "<Host(id='{}', name='{}', model='{}', host_type='{}', build='{}', "
            "validated='{}', switch_config_applied='{}', broken='{}', retired='{}', "
            "last_build='{}', can_self_schedule='{}', cloud='{}', default_cloud='{}', interfaces='{}', "
            "disks='{}', memory='{}', processors='{}', rack='{}', uloc='{}', blade='{}')>".format(
                self.id,
                self.name,
                self.model,
                self.host_type,
                self.build,
                self.validated,
                self.switch_config_applied,
                self.broken,
                self.retired,
                self.last_build,
                self.can_self_schedule,
                self.cloud,
                self.default_cloud,
                self.interfaces,
                self.disks,
                self.memory,
                self.processors,
                self.rack,
                self.uloc,
                self.blade,
            )
        )


class Schedule(Serialize, TimestampMixin, Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    start = Column(DateTime)
    end = Column(DateTime)
    build_start = Column(DateTime)
    build_end = Column(DateTime)

    # many-to-one parent
    assignment_id = Column(Integer, ForeignKey("assignments.id"))
    assignment = relationship("Assignment", foreign_keys=[assignment_id])

    # many-to-one parent
    host_id = Column(Integer, ForeignKey("hosts.id"))
    host = relationship("Host", foreign_keys=[host_id])

    def __repr__(self):
        return (
            "<Schedule(id='{}', start='{}', end='{}', build_start='{}', build_end='{}', "
            "assignment='{}', host='{}')>".format(
                self.id,
                self.start,
                self.end,
                self.build_start,
                self.build_end,
                self.assignment,
                self.host,
            )
        )
