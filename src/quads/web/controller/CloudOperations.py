import re
from datetime import datetime

from quads.config import Config
from quads.quads_api import APIBadRequest, APIServerException


class CloudOperations:

    def __init__(self, quads_api, foreman, loop):
        self.__quads_api = quads_api
        self.__foreman = foreman
        self.__loop = loop

    def __get_cloud_summary(self) -> list:
        """
        This method returns the cloud summary
        """
        clouds_summary = []
        summary_response = self.__quads_api.get_summary(data={})
        if summary_response.status_code == 200:
            clouds_summary = summary_response.json()
        return clouds_summary

    def __get_all_hosts(self):
        """
        This method returns the all hosts
        """
        all_hosts = self.__loop.run_until_complete(self.__foreman.get_all_hosts())
        return all_hosts

    def get_managed_nodes(self, cloud):
        """
        This method returns the scheduled nodes
        """
        managed_hosts = {}
        _ass_obj = self.__quads_api.get_active_cloud_assignment(cloud)
        _hosts = self.__quads_api.filter_hosts({"cloud": cloud, "retired": False, "broken": False})
        
        if _ass_obj:
            managed_hosts = {
                "name": cloud,
                "owner": _ass_obj.owner,
                "count": len(_hosts),
                "description": _ass_obj.description.strip(),
                "hosts": [self.__get_current_schedules(host.name) for host in _hosts],
            }
        elif cloud == Config["spare_pool_name"]:
            managed_hosts = {
                "name": cloud,
                "owner": "QUADS",
                "count": len(_hosts),
                "description": "Spare Pool",
                "hosts": [host.as_dict() for host in _hosts],
            }
            
        return managed_hosts

    def get_daily_utilization(self) -> int:
        """
        This method returns the daily utilization
        """
        _host_count = len(self.__quads_api.filter_hosts({"broken": False, "retired": False}))
        _schedules = len(self.__quads_api.get_current_schedules())
        if int(_host_count) == 0:
            _daily_utilization = "0"
        else:
            _daily_utilization = _schedules * 100 // _host_count
        return int(_daily_utilization)

    def get_cloud_summary_report(self) -> list:
        """
        This method returns the cloud summary
        """
        clouds_summary = []
        for cloud in self.__get_cloud_summary():
            if cloud.get("count") > 0:
                cloud_name = cloud.get("name")
                cloud["description"] = cloud["description"] if cloud["description"] else Config["spare_pool_description"]
                is_valid = cloud["validated"] or cloud_name == "cloud01"
                percent = 100
                if not is_valid:
                    scheduled_hosts = len(self.__quads_api.get_current_schedules({"cloud": cloud_name}))
                    moved_hosts = len(self.__quads_api.filter_hosts({"cloud": cloud_name}))
                    percent = (moved_hosts / scheduled_hosts) * 100
                cloud["is_valid"] = is_valid
                cloud["percent"] = int(percent)
                if cloud_name != 'cloud01':
                    if Config["openstack_management"]:
                        cloud["href_url_openstack"] = f"{Config['quads_url']}/instack/{cloud_name}_instackenv.json" if is_valid else "#"
                        cloud["href_url_text_openstack"] = "download" if is_valid else "validating..."
                    if Config["openshift_management"]:
                        cloud["href_url_openshift"] = f"{Config['quads_url']}/instack/{cloud_name}_ocpinventory.json" if is_valid else "#"
                        cloud["href_url_text_openshift"] = "download" if is_valid else "validating..."
                    cloud["href_color"] = "link-success" if is_valid else "link-danger"
                clouds_summary.append(cloud)
        return clouds_summary

    def __get_current_schedules(self, host: str) -> dict:
        """
        This method returns the current schedules
        """
        short_host = host.split(".")[0]
        _schedule_obj = None
        _schedules = self.__quads_api.get_current_schedules({"host": host})
        if _schedules:
            _schedule_obj = _schedules[0]
        if not _schedule_obj:
            _date_start = "∞"
            _date_end = "∞"
            total_time = "∞"
            total_time_left = "∞"
        else:
            _date_now = datetime.now()
            _date_start = _schedule_obj.start
            _date_end = _schedule_obj.end
            total_sec_left = (_date_end - _date_now).total_seconds()
            total_days = (_date_end - _date_start).days
            total_days_left = total_sec_left // 86400
            total_hours_left = ((total_sec_left / 86400) - total_days_left) * 24
            total_time = "%0d day(s)" % total_days
            total_time_left = "%0d day(s)" % total_days_left
            if total_hours_left > 1:
                total_time_left = "%s, %0d hour(s)" % (total_time_left, total_hours_left)
            _date_start = _date_start.strftime("%Y-%m-%d")
            _date_end = _date_end.strftime("%Y-%m-%d")
        current_schedule = {
            "short_name": short_host,
            "name": host,
            "start_date": _date_start,
            "end_date": _date_end,
            "total_time": total_time,
            "total_time_left": total_time_left,
        }
        return current_schedule

    def get_domain_broken_hosts(self, domain: str):
        """
        This method returns the broken hosts
        """
        broken_hosts = self.__quads_api.filter_hosts({"broken": True})
        return [host.as_dict() for host in broken_hosts if domain in host.name]

    def get_unmanaged_hosts(self, exclude_hosts: str):
        """
        This method returns the unmanaged hosts
        """
        all_hosts = self.__get_all_hosts()
        blacklist = re.compile("|".join([re.escape(word) for word in exclude_hosts.split("|")]))
        mgmt_hosts = {}
        for host, properties in all_hosts.items():
            if not blacklist.search(host):
                if properties.get("sp_name", False):
                    properties["host_ip"] = all_hosts.get(host, {"ip": None})["ip"]
                    properties["host_mac"] = all_hosts.get(host, {"mac": None})["mac"]
                    properties["ip"] = properties.get("sp_ip")
                    properties["mac"] = properties.get("sp_mac")
                    mgmt_hosts[properties.get("sp_name")] = properties
        unmanaged_hosts = []
        for host, properties in mgmt_hosts.items():
            real_host = host[5:]
            try:
                host_obj = self.__quads_api.get_host(real_host)
            except (APIBadRequest, APIServerException):
                host_obj = None

            if not host_obj:
                short_host = real_host.split(".")[0]
                unmanaged_hosts.append(
                    {
                        "name": host,
                        "short_name": short_host,
                    }
                )
        return unmanaged_hosts

    def get_vlans_list(self):
        """
        This method returns the vlans list
        """
        vlans_list = []
        vlans = self.__quads_api.get_vlans()
        for vlan in vlans:
            assignment_obj = self.__quads_api.filter_assignments({"active": True, "vlan.vlan_id": vlan.vlan_id})
            assignment_obj = assignment_obj[0] if assignment_obj else None
            cloud_current_count = 0
            cloud_obj = None
            if assignment_obj:
                cloud_obj = self.__quads_api.filter_clouds({"name": assignment_obj.cloud.name})
                if cloud_obj:
                    cloud_obj = cloud_obj[0]
                    cloud_current_count = len(self.__quads_api.get_current_schedules({"cloud": cloud_obj.name}))
            if assignment_obj and cloud_current_count > 0 and cloud_obj:
                owner = assignment_obj.owner
                ticket = assignment_obj.ticket
                cloud_name = cloud_obj.name
            else:
                owner = "nobody"
                ticket = ""
                cloud_name = ""
            columns = {
                "vlanid": vlan.vlan_id,
                "iprange": vlan.ip_range.strip(","),
                "netmask": vlan.netmask,
                "gateway": vlan.gateway,
                "ipfree": vlan.ip_free,
                "owner": owner,
                "ticket": ticket,
                "cloud": cloud_name,
            }

            vlans_list.append(columns)
        return vlans_list
