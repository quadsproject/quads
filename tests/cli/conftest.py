from datetime import datetime, timedelta

import pytest

from quads.server.app import create_app, user_datastore
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.disk import DiskDao
from quads.server.dao.host import HostDao
from quads.server.dao.interface import InterfaceDao
from quads.server.dao.memory import MemoryDao
from quads.server.dao.processor import ProcessorDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from quads.server.database import drop_all, populate, init_db
from tests.cli.config import (
    CLOUD,
    HOST_TYPE,
    DEFAULT_CLOUD,
    HOST1,
    MODEL1,
    HOST2,
    MODEL2,
    DEFINE_CLOUD,
    REMOVE_CLOUD,
    MOD_CLOUD,
    IFNAME1,
    IFVENDOR1,
    IFBIOSID1,
    IFMAC1,
    IFIP1,
    IFPORT1,
    IFSPEED,
)


@pytest.fixture(autouse=True, scope="session")
def test_client():
    """
    | Creates a test client for the app from the testing config.
    | Drops and then initializes the database and populates it with default users.
    """
    flask_app = create_app("quads.server.config.TestingConfig")

    with flask_app.test_client() as testing_client:
        with flask_app.app_context():
            drop_all(flask_app.config)
            init_db(flask_app.config)
            populate(user_datastore)
            yield testing_client


@pytest.fixture(autouse=True, scope="package")
def populate_db():

    today = datetime.strptime(datetime.now().strftime("%Y-%m-%d %H:%M"), "%Y-%m-%d %H:%M")
    tomorrow = today + timedelta(weeks=2)

    cloud = CloudDao.create_cloud(CLOUD)
    default_cloud = CloudDao.create_cloud(DEFAULT_CLOUD)
    remove_cloud = CloudDao.create_cloud(REMOVE_CLOUD)
    mod_cloud = CloudDao.create_cloud(MOD_CLOUD)
    host1 = HostDao.create_host(HOST1, MODEL1, HOST_TYPE, CLOUD)
    host2 = HostDao.create_host(HOST2, MODEL2, HOST_TYPE, CLOUD)
    InterfaceDao.create_interface(
        HOST1,
        IFNAME1,
        IFBIOSID1,
        IFMAC1,
        IFIP1,
        IFPORT1,
        IFSPEED,
        IFVENDOR1,
        True,
        False,
    )
    DiskDao.create_disk(HOST1, "NVME", 4096, 10)
    DiskDao.create_disk(HOST1, "SATA", 4096, 5)
    MemoryDao.create_memory(HOST1, "DIMM1", 2048)
    MemoryDao.create_memory(HOST1, "DIMM2", 2048)
    ProcessorDao.create_processor(HOST1, "P1", "Intel", "i7", 2, 4, processor_type="CPU")
    vlan1 = VlanDao.create_vlan("192.168.1.1", 122, "192.168.1.1/22", "255.255.255.255", 1)
    vlan2 = VlanDao.create_vlan("192.168.1.2", 122, "192.168.1.2/22", "255.255.255.255", 2)
    assignment = AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], cloud.name, vlan1.vlan_id)
    AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], mod_cloud.name, vlan2.vlan_id)
    ScheduleDao.create_schedule(
        today,
        tomorrow,
        assignment,
        host1,
    )

    yield

    host1 = HostDao.get_host(HOST1)
    host2 = HostDao.get_host(HOST2)
    cloud = CloudDao.get_cloud(CLOUD)
    default_cloud = CloudDao.get_cloud(DEFAULT_CLOUD)
    define_cloud = CloudDao.get_cloud(DEFINE_CLOUD)
    remove_cloud = CloudDao.get_cloud(REMOVE_CLOUD)
    mod_cloud = CloudDao.get_cloud(MOD_CLOUD)
    schedules = ScheduleDao.get_current_schedule(host=host1, cloud=cloud)

    if schedules:
        ScheduleDao.remove_schedule(schedules[0].id)
        AssignmentDao.remove_assignment(schedules[0].assignment_id)

    assignments = AssignmentDao.get_assignments()
    for ass in assignments:
        AssignmentDao.remove_assignment(ass.id)

    if host1:
        HostDao.remove_host(name=HOST1)

    if host2:
        HostDao.remove_host(name=HOST2)

    if cloud:
        CloudDao.remove_cloud(CLOUD)

    if define_cloud:
        CloudDao.remove_cloud(DEFINE_CLOUD)

    if remove_cloud:
        CloudDao.remove_cloud(REMOVE_CLOUD)

    if mod_cloud:
        CloudDao.remove_cloud(MOD_CLOUD)

    if default_cloud:
        CloudDao.remove_cloud(DEFAULT_CLOUD)
