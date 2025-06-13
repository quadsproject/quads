import os
from json import JSONDecodeError
from typing import List, Optional
from urllib import parse as url_parse
from urllib.parse import urlencode

from requests import Response, Session
from requests.adapters import HTTPAdapter, Retry
from requests.auth import HTTPBasicAuth

from quads.server.models import Assignment, Cloud, Host, Interface, Schedule, Vlan


class APIServerException(Exception):
    pass


class APIBadRequest(Exception):
    pass


class Generic:
    @classmethod
    def from_dict(cls, dict):
        obj = cls()
        obj.__dict__.update(dict)
        return obj


class QuadsBase(object):
    """
    Base class for the Quads API
    """

    def __init__(self, config):
        self.config = config
        self.base_url = config.API_URL
        self.session = Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.auth = HTTPBasicAuth(self.config.get("quads_api_username"), self.config.get("quads_api_password"))

    # Base functions
    def get(self, endpoint: str) -> Response:
        _response = self.session.get(os.path.join(self.base_url, endpoint), verify=False, auth=self.auth)
        if _response.status_code == 500:
            raise APIServerException("Check the flask server logs")
        if _response.status_code == 400:
            try:
                response_json = _response.json()
            except JSONDecodeError:
                raise APIBadRequest("Failed to parse response")
            raise APIBadRequest(response_json.get("message"))
        return _response

    def post(self, endpoint, data) -> Response:
        _response = self.session.post(
            os.path.join(self.base_url, endpoint),
            json=data,
            verify=False,
            auth=self.auth,
        )
        if _response.status_code == 500:
            raise APIServerException("Check the flask server logs")
        if _response.status_code == 400:
            response_json = _response.json()
            raise APIBadRequest(response_json.get("message"))
        return _response

    def patch(self, endpoint, data) -> Response:
        _response = self.session.patch(
            os.path.join(self.base_url, endpoint),
            json=data,
            verify=False,
            auth=self.auth,
        )
        if _response.status_code == 500:
            raise APIServerException("Check the flask server logs")
        if _response.status_code == 400:
            response_json = _response.json()
            raise APIBadRequest(response_json.get("message"))
        return _response

    def delete(self, endpoint) -> Response:
        _response = self.session.delete(os.path.join(self.base_url, endpoint), verify=False, auth=self.auth)
        if _response.status_code == 500:
            raise APIServerException("Check the flask server logs")
        if _response.status_code == 400:
            response_json = _response.json()
            raise APIBadRequest(response_json.get("message"))
        return _response


class QuadsApi(QuadsBase):
    """
    A python interface into the Quads API
    """

    # Hosts
    def get_hosts(self) -> List[Host]:
        response = self.get("hosts")
        hosts_json = response.json()
        hosts = []
        for host in hosts_json:
            host_obj = Host().from_dict(data=host)
            hosts.append(host_obj)
        return hosts

    def get_host_models(self):
        response = self.get("hosts?group_by=model")
        return response.json()

    def get_host_racks(self, retired: bool = False, broken: bool = False):
        response = self.get(f"hosts?retired={retired}&broken={broken}&group_by=rack")
        return response.json()

    def filter_hosts(self, data) -> List[Host]:
        url_params = url_parse.urlencode(data)
        response = self.get(f"hosts?{url_params}")
        hosts = []
        for host in response.json():
            host_obj = Host().from_dict(data=host)
            hosts.append(host_obj)
        return hosts

    def filter_clouds(self, data) -> List[Cloud]:
        url_params = url_parse.urlencode(data)
        response = self.get(f"clouds?{url_params}")
        clouds = []
        for cloud in response.json():
            host_obj = Cloud().from_dict(data=cloud)
            clouds.append(host_obj)
        return clouds

    def filter_assignments(self, data) -> List[Assignment]:
        url_params = url_parse.urlencode(data)
        response = self.get(f"assignments?{url_params}")
        assignments = []
        for ass in response.json():
            ass_obj = Assignment().from_dict(data=ass)
            assignments.append(ass_obj)
        return assignments

    def get_host(self, hostname) -> Optional[Host]:
        host_obj = None
        response = self.get(os.path.join("hosts", hostname))
        obj_json = response.json()
        if obj_json:
            host_obj = Host().from_dict(data=obj_json)
        return host_obj

    def create_host(self, data) -> Host:
        response = self.post(os.path.join("hosts"), data)
        data = response.json()
        host_obj = Host().from_dict(data)
        return host_obj

    def update_host(self, hostname, data) -> Response:
        return self.patch(os.path.join("hosts", hostname), data)

    def remove_host(self, hostname) -> Response:
        return self.delete(os.path.join("hosts", hostname))

    def is_available(self, hostname, data) -> bool:
        url_params = url_parse.urlencode(data)
        uri = os.path.join("available", hostname)
        response = self.get(f"{uri}?{url_params}")
        return True if "true" in response.text.lower() else False

    # Clouds
    def get_clouds(self) -> List[Cloud]:
        response = self.get("clouds")
        clouds = []
        for cloud in response.json():
            clouds.append(Cloud(**cloud))
        return [cloud for cloud in sorted(clouds, key=lambda x: x.name)]

    def get_free_clouds(self) -> List[Cloud]:
        response = self.get("clouds/free/")
        clouds = []
        for cloud in response.json():
            clouds.append(Cloud(**cloud))
        return clouds

    def get_cloud(self, cloud_name) -> Optional[Cloud]:
        cloud_obj = None
        response = self.get(f"clouds?name={cloud_name}")
        obj_json = response.json()
        if obj_json:
            cloud_response = obj_json[0]
            cloud_obj = Cloud(**cloud_response)
        return cloud_obj

    def get_summary(self, data: dict) -> Response:
        url_params = url_parse.urlencode(data)
        endpoint = os.path.join("clouds", "summary")
        url = f"{endpoint}"
        if data:
            url = f"{endpoint}?{url_params}"
        response = self.get(url)
        return response

    def insert_cloud(self, data) -> Response:
        return self.post("clouds", data)

    def update_cloud(self, cloud_name, data) -> Response:
        return self.patch(os.path.join("clouds", cloud_name), data)

    def remove_cloud(self, cloud_name) -> Response:
        return self.delete(os.path.join("clouds", cloud_name))

    # Schedules
    def get_schedules(self, data: dict = None) -> List[Schedule]:
        if data is None:
            data = {}
        url_params = url_parse.urlencode(data)
        url = "schedules"
        if url_params:
            url = f"{url}?{url_params}"
        response = self.get(url)
        schedules = []
        for schedule in response.json():
            schedules.append(Schedule().from_dict(schedule))
        return schedules

    def get_current_schedules(self, data: dict = None) -> List[Schedule]:
        if data is None:
            data = {}
        endpoint = os.path.join("schedules", "current")
        url = f"{endpoint}"
        if data:
            url_params = url_parse.urlencode(data)
            url = f"{endpoint}?{url_params}"
        response = self.get(url)
        schedules = []
        for schedule in response.json():
            schedules.append(Schedule().from_dict(schedule))
        return schedules

    def get_schedule(self, schedule_id: int) -> Schedule:
        schedule_obj = None
        url = os.path.join("schedules", str(schedule_id))
        response = self.get(url)
        obj_json = response.json()
        if obj_json:
            schedule_obj = Schedule(**obj_json)
        return schedule_obj

    def get_future_schedules(self, data: dict = None) -> List[Schedule]:
        if data is None:
            data = {}
        url_params = url_parse.urlencode(data)
        endpoint = os.path.join("schedules", "future")
        url = f"{endpoint}"
        if data:
            url = f"{endpoint}?{url_params}"
        response = self.get(url)
        schedules = []
        for schedule in response.json():
            schedules.append(Schedule(**schedule))
        return schedules

    def update_schedule(self, schedule_id, data) -> Response:
        return self.patch(os.path.join("schedules", str(schedule_id)), data)

    def remove_schedule(self, schedule_id) -> Response:
        return self.delete(os.path.join("schedules", str(schedule_id)))

    def insert_schedule(self, data) -> Response:
        return self.post("schedules", data)

    # Available
    def get_available(self) -> List[Host]:
        response = self.get("available")
        hosts = []
        for host in response.json():
            hosts.append(Host(**host))
        return hosts

    def filter_available(self, data) -> List[Host]:
        response = self.get(f"available?{urlencode(data)}")
        hosts = []
        for host in response.json():
            host_resp = self.get(f"hosts/{host}").json()
            hosts.append(Host().from_dict(host_resp))
        return hosts

    # Assignments
    def insert_assignment(self, data) -> Response:
        return self.post("assignments", data)

    def update_assignment(self, assignment_id, data) -> Response:
        return self.patch(os.path.join("assignments", str(assignment_id)), data)

    def update_notification(self, notification_id, data) -> Response:
        return self.patch(os.path.join("notifications", str(notification_id)), data)

    def get_active_cloud_assignment(self, cloud_name) -> Assignment:
        response = self.get(os.path.join("assignments/active", cloud_name))
        data = response.json()
        assignment = None
        if data:
            assignment = Assignment().from_dict(data)

        return assignment

    def get_active_assignments(self) -> List[Assignment]:
        response = self.get("assignments/active")
        data = response.json()
        assignments = []
        for ass in data:
            ass_object = Assignment().from_dict(ass)
            assignments.append(ass_object)

        return assignments

    # Interfaces
    def get_host_interface(self, hostname) -> List[Interface]:
        response = self.get(os.path.join("hosts", hostname, "interfaces"))
        data = response.json()
        interfaces = []
        for interface in data:
            interface_obj = Interface().from_dict(interface)
            interfaces.append(interface_obj)
        return interfaces

    def get_interfaces(self) -> Response:
        return self.get("interfaces")

    def update_interface(self, hostname, data) -> Response:
        return self.patch(os.path.join("interfaces", hostname), data)

    def remove_interface(self, hostname, if_name) -> Response:
        return self.delete(os.path.join("interfaces", hostname, if_name))

    def create_interface(self, hostname, data) -> Response:
        return self.post(os.path.join("interfaces", hostname), data)

    # Memory
    def create_memory(self, hostname, data) -> Response:
        return self.post(os.path.join("memory", hostname), data)

    def remove_memory(self, memory_id) -> Response:
        return self.delete(os.path.join("memory", memory_id))

    # Disks
    def create_disk(self, hostname, data) -> Response:
        return self.post(os.path.join("disks", hostname), data)

    def update_disk(self, hostname, data) -> Response:
        return self.patch(os.path.join("disks", hostname), data)

    def remove_disk(self, disk_id) -> Response:
        return self.delete(os.path.join("disks", disk_id))

    # Processor
    def create_processor(self, hostname, data) -> Response:
        return self.post(os.path.join("processors", hostname), data)

    def remove_processor(self, processor_id) -> Response:
        return self.delete(os.path.join("processors", processor_id))

    # Vlans
    def get_vlans(self) -> List[Vlan]:
        response = self.get("vlans")
        vlans = []
        for vlan in response.json():
            vlans.append(Vlan(**vlan))
        return [vlan for vlan in sorted(vlans, key=lambda x: x.vlan_id)]

    def get_vlan(self, vlan_id) -> Response:
        return self.get(os.path.join("vlans", str(vlan_id)))

    def update_vlan(self, vlan_id, data: dict) -> Response:
        return self.patch(os.path.join("vlans", str(vlan_id)), data)

    # Processor
    def create_vlan(self, data: dict) -> Response:
        return self.post("vlans", data)

    # Moves
    def get_moves(self, date=None) -> List:
        url = "moves"
        if date:
            url_params = url_parse.urlencode({"date": date})
            url = f"moves?{url_params}"
        response = self.get(url)
        data = response.json()
        return data

    def get_version(self) -> Response:
        return self.get("version")

    def get_os_list(self) -> List:
        response = self.get("hosts/os_list")
        data = response.json()
        return data
