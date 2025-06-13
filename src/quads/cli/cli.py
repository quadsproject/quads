import asyncio
import functools
import logging
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from json import JSONDecodeError
from tempfile import NamedTemporaryFile
from typing import Optional, Tuple

import yaml
from jinja2 import Template
from requests import ConnectionError

from quads.config import Config as conf
from quads.exceptions import BaseQuadsException, CliException
from quads.helpers.utils import first_day_month, last_day_month
from quads.quads_api import APIBadRequest, APIServerException
from quads.quads_api import QuadsApi as Quads
from quads.server.models import Assignment
from quads.tools import reports
from quads.tools.external.badfish import Badfish
from quads.tools.external.jira import Jira, JiraException
from quads.tools.foreman_heal import rbac as foreman_heal
from quads.tools.make_instackenv_json import main as regen_instack
from quads.tools.move_and_rebuild import move_and_rebuild, switch_config
from quads.tools.notify import main as notify
from quads.tools.simple_table_web import main as regen_heatmap
from quads.tools.validate_env import main as validate_env

default_move_command = "/opt/quads/quads/tools/move_and_rebuild.py"


class QuadsCli:
    ACTION_PREFIX = "action_"

    quads: Quads
    logger: logging.Logger
    cli_args: dict

    def __init__(self, quads: Quads, logger: logging.Logger):
        self.quads = quads
        self.logger = logger

    @staticmethod
    def _confirmation_dialog(msg, default_choice="n"):
        return (input(msg) or default_choice).lower() in ("y", "yes")

    def run(self, action: str, cli_args: dict) -> Optional[int]:
        self.cli_args = cli_args
        self.logger.debug(self.cli_args)

        if action:
            # action method should always be available
            # unless not implemented on this class yet
            action_meth_name = self.ACTION_PREFIX + action
            action_meth = getattr(self, action_meth_name, None)
            self.logger.debug(f"Action: {action}; {action_meth}")

            assert action_meth is not None and callable(
                action_meth
            ), f"Missing callable action method '{action_meth_name}', not implemented yet?"

            try:
                exit_code = action_meth()
            except CliException as exc:
                raise CliException(str(exc))

            return exit_code

        host = self.cli_args.get("host")
        if host:
            try:
                _host = self.quads.get_host(host)
                _host_dict = _host.as_dict()
                yaml_str = yaml.dump(_host_dict, default_flow_style=False, sort_keys=False)
                self.logger.info("\n" + yaml_str)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))
            return 0

        cloud = self.cli_args.get("cloud")
        if cloud:
            try:
                _hosts = self.quads.filter_hosts({"cloud": cloud})
                for host in _hosts:
                    self.logger.info(host.name)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))
            return 0

        # default action
        try:
            clouds = self.quads.get_clouds()
            hosts = self.quads.get_hosts()
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        _date = datetime.now()
        if self.cli_args.get("datearg"):
            _date = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M")
        for cloud in clouds:
            if cloud.name == "cloud01":
                available = []
                for host in hosts:
                    start_date = ":".join(_date.isoformat().split(":")[:-1])
                    payload = {
                        "start": start_date,
                        "end": start_date,
                    }
                    try:
                        if self.quads.is_available(host.name, payload):
                            available.append(host)
                    except Exception as ex:
                        raise CliException(str(ex))
                if available:
                    self.logger.info(f"{cloud.name}:")
                    for host in available:
                        self.logger.info(f"  - {host.name}")
            else:
                date_str = ":".join(_date.isoformat().split(":")[:-1])
                payload = {"cloud": cloud.name, "date": date_str}
                try:
                    schedules = self.quads.get_current_schedules(payload)
                except (APIServerException, APIBadRequest) as ex:
                    raise CliException(str(ex))
                if schedules:
                    self.logger.info(f"{cloud.name}:")
                    for schedule in schedules:
                        self.logger.info(f"  - {schedule.host.name}")

        return 0

    def clear_field(self, host, key):
        dispatch_remove = {
            "disks": self.quads.remove_disk,
            "memory": self.quads.remove_memory,
            "processors": self.quads.remove_processor,
            "interfaces": self.quads.remove_interface,
        }
        field = getattr(host, key)
        if field is None:  # pragma: no cover
            raise CliException(f"{key} is not a Host property")

        for obj in field:  # pragma: no cover
            try:
                _id = obj.id
                if key == "interfaces":
                    _id = obj.name

                remove_func = dispatch_remove.get(key)
                # remove_interface() needs hostname & interface name
                if key == "interfaces":
                    remove_func(host.name, str(_id))
                else:
                    remove_func(str(_id))
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))

    def _filter_kwargs(self, filter_args):
        kwargs = {}
        ops = {
            "==": "",
            "!=": "__ne",
            "<": "__lt",
            "<=": "__lte",
            ">": "__gt",
            ">=": "__gte",
        }
        conditions = filter_args.split(",")
        for condition in conditions:
            op_found = False
            for op, op_suffix in ops.items():
                if op in condition:
                    op_found = True
                    k, v = condition.split(op)
                    if v.startswith("="):
                        op = f"{op}="
                        op_suffix = ops.get(op)
                        v = v[1:]
                    keys = k.split(".")

                    try:
                        value = int(v)
                    except ValueError:
                        value = v

                    if isinstance(value, str):
                        if value.lower() == "false":
                            value = False
                        elif value.lower() == "true":
                            value = True

                    if keys[0].strip().lower() in [
                        "disks",
                        "interfaces",
                        "processors",
                        "memory",
                    ]:

                        key = f"{keys[0]}.{'__'.join(keys[1:])}{op_suffix}".strip()
                        if kwargs.get(key, False):
                            kwargs[key].update(value)
                        else:
                            kwargs[key] = value
                    else:
                        if keys[0].strip().lower() == "model":
                            if str(value).upper() not in conf["models"].upper().split(","):
                                self.logger.warning(f"Accepted model names are: {conf['models']}")
                                raise CliException("Model type not recognized.")

                        if isinstance(value, str):
                            value = value.upper()
                        query = {f"{'__'.join(keys)}{op_suffix}": value}
                        kwargs.update(query)
                    break
            if not op_found:
                self.logger.warning(f"Condition: {condition}")
                self.logger.warning(f"Accepted operators: {', '.join(ops.keys())}")
                raise CliException("A filter was defined but not parsed correctly. Check filter operator.")
        if not kwargs:  # pragma: no cover
            raise CliException("A filter was defined but not parsed correctly. Check filter syntax.")
        return kwargs

    def _output_json_result(self, request, data):
        try:
            if request.status_code == 204:
                self.logger.info("Successfully removed")
            else:
                js = request.json()
                self.logger.debug("%s %s: %s" % (request.status_code, request.reason, data))
                if request.request.method == "POST" and request.status_code == 200:
                    self.logger.info("Successful request")
                if js.get("result"):
                    for result in js["result"]:
                        if isinstance(result, list):
                            for line in result:
                                self.logger.info(line)
                        else:
                            self.logger.info(result)
        except JSONDecodeError:  # pragma: no cover
            self.logger.debug(request.text)
            raise CliException("Could not parse json reply")

    def action_version(self):
        try:
            response = self.quads.get_version()
            self.logger.info(response.content.decode("utf-8"))
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

    def action_ls_broken(self):
        payload = {"broken": True}
        try:
            _hosts = self.quads.filter_hosts(payload)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        for host in _hosts:
            self.logger.info(host.name)

    def action_ls_retired(self):
        payload = {"retired": True}
        try:
            _hosts = self.quads.filter_hosts(payload)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        for host in _hosts:
            self.logger.info(host.name)

    def _call_api_action(self, action: str):
        try:
            assignments = self.quads.get_active_assignments()
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        for ass in assignments:
            self.logger.info(f"{ass.cloud.name}: {getattr(ass, action)}")

    def action_owner(self):
        self._call_api_action("owner")

    def action_ticket(self):
        self._call_api_action("ticket")

    def action_qinq(self):
        self._call_api_action("qinq")

    def action_wipe(self):
        self._call_api_action("wipe")

    def action_ccuser(self):
        self._call_api_action("ccuser")

    def action_interface(self):
        hostname = self.cli_args.get("host")
        if not hostname:
            raise CliException("Missing option. --host option is required for --ls-interface.")

        try:
            self.quads.get_host(hostname)

            data = self.quads.get_host_interface(hostname)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        if data:
            for interface in sorted(data, key=lambda k: k.name):
                self.logger.info(f"interface: {interface.name}")
                self.logger.info(f"  bios id: {interface.bios_id}")
                self.logger.info(f"  mac address: {interface.mac_address}")
                self.logger.info(f"  switch ip: {interface.switch_ip}")
                self.logger.info(f"  port: {interface.switch_port}")
                self.logger.info(f"  speed: {interface.speed}")
                self.logger.info(f"  vendor: {interface.vendor}")
                self.logger.info(f"  pxe_boot: {interface.pxe_boot}")
                self.logger.info(f"  maintenance: {interface.maintenance}")
        else:
            self.logger.error(f"No interfaces defined for {hostname}")

    def action_memory(self):
        hostname = self.cli_args.get("host")
        if hostname is None:
            raise CliException("Missing option. --host option is required for --ls-memory.")

        try:
            host = self.quads.get_host(hostname)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        if host.memory:
            for i, memory in enumerate(host.memory):
                self.logger.info(f"memory: {memory.handle}")
                self.logger.info(f"  size: {memory.size_gb}")
        else:
            self.logger.error(f"No memory defined for {hostname}")

    def action_disks(self):
        hostname = self.cli_args.get("host")
        if hostname is None:
            raise CliException("Missing option. --host option is required for --ls-disks.")

        try:
            host = self.quads.get_host(hostname)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        if host.disks:
            for i, disk in enumerate(host.disks):
                self.logger.info(f"disk{i}:")
                self.logger.info(f"  type: {disk.disk_type}")
                self.logger.info(f"  size: {disk.size_gb}")
                self.logger.info(f"  count: {disk.count}")
        else:
            self.logger.error(f"No disks defined for {hostname}")

    def action_processors(self):
        hostname = self.cli_args.get("host")
        if not hostname:
            raise CliException("Missing option. --host option is required for --ls-processors.")

        try:
            host = self.quads.get_host(hostname)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        if host.processors:
            for i, processor in enumerate(host.processors):
                self.logger.info(f"processor: {processor.handle}")
                self.logger.info(f"  vendor: {processor.vendor}")
                self.logger.info(f"  product: {processor.product}")
                self.logger.info(f"  cores: {processor.cores}")
                self.logger.info(f"  threads: {processor.threads}")
        else:
            self.logger.error(f"No processors defined for {hostname}")

    def action_ls_vlan(self):
        try:
            _vlans = self.quads.get_vlans()
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        if _vlans:
            for vlan in _vlans:
                payload = {"vlan.vlan_id": vlan.vlan_id, "active": True}
                try:
                    assignments = self.quads.filter_assignments(payload)
                except (APIServerException, APIBadRequest) as ex:
                    raise CliException(str(ex))
                cloud_assigned = "Free"
                if assignments:
                    cloud_assigned = assignments[0].cloud.name
                self.logger.info(f"{vlan.vlan_id}: {cloud_assigned}")
        else:
            self.logger.warning("No VLANs found.")

    def action_schedule(self):
        _kwargs = {}
        if self.cli_args.get("host"):
            try:
                _host = self.quads.get_host(self.cli_args.get("host"))
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))

            _kwargs["host"] = _host.name
            self.logger.info("Default cloud: %s" % _host.default_cloud.name)
            try:
                _current_schedule = self.quads.get_current_schedules(_kwargs)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))
            if _current_schedule:
                _current_cloud = _current_schedule[0].assignment.cloud.name
                if _current_cloud != _host.default_cloud.name:
                    self.logger.info("Current cloud: %s" % _current_cloud)
                    self.logger.info("Current schedule: %s" % _current_schedule[0].id)
                else:
                    self.logger.info("Current cloud: %s" % _host.default_cloud.name)
            else:
                self.logger.info("Current cloud: %s" % _host.default_cloud.name)
            try:
                _host_schedules = self.quads.get_schedules(_kwargs)
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            if _host_schedules:
                for schedule in _host_schedules:
                    _cloud_name = schedule.assignment.cloud.name
                    start = ":".join(schedule.start.isoformat().split(":")[:-1])
                    end = ":".join(schedule.end.isoformat().split(":")[:-1])
                    self.logger.info(f"{schedule.id}| start={start}, end={end}, cloud={_cloud_name}")
        else:
            try:
                _clouds = self.quads.get_clouds()
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            for cloud in _clouds:
                self.logger.info("%s:" % cloud.name)
                _kwargs["cloud"] = cloud.name
                if cloud.name == conf.get("spare_pool_name"):
                    if self.cli_args.get("datearg"):
                        _date = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M")
                        _date_iso = ":".join(_date.isoformat().split(":")[:-1])
                        data = {
                            "start": _date_iso,
                            "end": _date_iso,
                        }
                        try:
                            available_hosts = self.quads.filter_available(data)
                        except (
                            APIServerException,
                            APIBadRequest,
                        ) as ex:  # pragma: no cover
                            raise CliException(str(ex))

                        for host in available_hosts:
                            self.logger.info(host.name)
                else:
                    payload = {"cloud": cloud.name}
                    try:
                        _hosts = self.quads.filter_hosts(payload)
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
                    for host in _hosts:
                        self.logger.info(host.name)

    def action_ls_hosts(self):
        kwargs = {"retired": False}
        try:
            if self.cli_args.get("filter"):
                filter_args = self._filter_kwargs(self.cli_args.get("filter"))
                kwargs.update(filter_args)
            hosts = self.quads.filter_hosts(kwargs)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        if hosts:
            for host in sorted(hosts, key=lambda k: k.name):
                self.logger.info(host.name)
        else:
            self.logger.warning("No hosts found.")

        return 0

    def action_ls_clouds(self):
        try:
            clouds = self.quads.get_clouds()
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        if clouds:
            for cloud in sorted(clouds, key=lambda k: k.name):
                self.logger.info(cloud.name)
        else:
            self.logger.warning("No clouds found.")

        return 0

    def action_free_cloud(self):
        try:
            _clouds = self.quads.get_free_clouds()
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        for cloud in _clouds:
            cloud_reservation_lock = int(conf["cloud_reservation_lock"])
            last_redefined = datetime.strptime(str(cloud.last_redefined), "%a, %d %b %Y %H:%M:%S %Z")
            lock_release = last_redefined + timedelta(hours=cloud_reservation_lock)
            cloud_string = f"{cloud.name}"
            if lock_release > datetime.now():
                time_left = lock_release - datetime.now()
                hours = time_left.total_seconds() // 3600
                minutes = (time_left.total_seconds() % 3600) // 60
                cloud_string += " (reserved: %dhr %dmin remaining)" % (
                    hours,
                    minutes,
                )
            self.logger.info(cloud_string)

    def action_available(self):
        kwargs = {}
        host_kwargs = {}
        _filter = self.cli_args.get("filter")
        _schedstart = self.cli_args.get("schedstart")
        _schedend = self.cli_args.get("schedend")
        _start = _end = "T".join(":".join(datetime.now().isoformat().split(":")[:-1]).split())

        if _filter:
            filter_args = self._filter_kwargs(_filter)
            host_kwargs.update(filter_args)
            kwargs.update(filter_args)

        if _schedstart:
            _start_date = datetime.strptime(_schedstart, "%Y-%m-%d %H:%M")
            kwargs["start"] = _start_date
            _start = _start_date.isoformat()[:-3]

        if _schedend:
            _end_date = datetime.strptime(_schedend, "%Y-%m-%d %H:%M")
            kwargs["end"] = _end_date
            _end = _end_date.isoformat()[:-3]

        available = []
        current = []
        try:
            all_hosts = self.quads.filter_hosts(host_kwargs)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        omit_cloud_arg = self.cli_args.get("omitcloud")
        if omit_cloud_arg:
            try:
                self.quads.get_cloud(omit_cloud_arg)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(str(ex))

        for host in all_hosts:
            data = {"start": _start, "end": _end}
            # TODO: check return on this below
            try:
                if self.quads.is_available(host.name, data):
                    current_schedule = self.quads.get_current_schedules({"host": host.name})
                    if current_schedule:
                        if (
                            host.default_cloud.name == conf["spare_pool_name"]
                            and current_schedule[0].assignment.cloud.name != omit_cloud_arg
                        ):
                            current.append(host.name)
                    else:
                        if host.default_cloud.name == conf["spare_pool_name"]:
                            available.append(host.name)
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))

        for host in available:
            self.logger.info(host)
        for host in current:
            self.logger.warning(host)

    def action_report_scheduled(self):
        if self.cli_args.get("months") is None and self.cli_args.get("year") is None:
            raise CliException("Missing argument. --months or --year must be provided.")

        now = datetime.now()
        if self.cli_args.get("year"):
            months = 12
            year = self.cli_args.get("year")
        else:
            months = self.cli_args.get("months")
            year = now.year

        reports.report_scheduled(self.logger, int(months), int(year))

    def _helper_report_start_end(self) -> Tuple[datetime, datetime]:
        now = datetime.now()
        if self.cli_args.get("schedstart") and self.cli_args.get("schedend") is None:
            self.cli_args["schedend"] = self.cli_args.get("schedstart")

        if not self.cli_args.get("schedstart") and self.cli_args.get("schedend"):
            self.cli_args["schedstart"] = str(now)[:-10]

        if not self.cli_args.get("schedstart") and not self.cli_args.get("schedend"):
            start = first_day_month(now)
            self.cli_args["schedstart"] = str(start)[:-10]
            end = last_day_month(now)
            self.cli_args["schedend"] = str(end)[:-10]

        _start = datetime.strptime(self.cli_args.get("schedstart"), "%Y-%m-%d %H:%M")
        _end = datetime.strptime(self.cli_args.get("schedend"), "%Y-%m-%d %H:%M")

        return _start, _end

    def action_report_available(self):
        start, end = self._helper_report_start_end()
        reports.report_available(self.logger, start, end)

    def action_report_detailed(self):
        start, end = self._helper_report_start_end()
        reports.report_detailed(self.logger, start, end)

    def action_extend(self):
        weeks = self.cli_args.get("weeks")
        date_arg = self.cli_args.get("datearg")
        cloud_name = self.cli_args.get("cloud")
        host_name = self.cli_args.get("host")
        check = self.cli_args.get("check")

        _date = None
        end_date = None

        if not weeks and not date_arg:
            msg = "Missing option. Need --weeks or --date when using --extend"
            raise CliException(msg)

        if not cloud_name and not host_name:
            msg = "Missing option. At least one of either --host or --cloud is required."
            raise CliException(msg)

        if weeks:
            try:
                weeks = int(weeks)
            except ValueError:
                raise CliException("The value of --weeks must be an integer")

        dispatch = {"cloud": self.quads.get_cloud, "host": self.quads.get_host}
        dispatch_key = "cloud" if cloud_name else "host"
        data_dispatch = {"cloud": cloud_name} if cloud_name else {"host": host_name}

        try:
            dispatched_obj = dispatch[dispatch_key](data_dispatch[dispatch_key])
            if not dispatched_obj:  # pragma: no cover
                raise CliException(f"{dispatch_key.capitalize()} not found")

            schedules = self.quads.get_current_schedules(data_dispatch)
            if not schedules:
                self.logger.warning(f"The selected {dispatch_key} does not have any active schedules")
                future_schedules = self.quads.get_future_schedules(data_dispatch)
                if not future_schedules:
                    return

                if not self._confirmation_dialog(
                    "Would you like to extend a future allocation of " f"{data_dispatch[dispatch_key]}? (y/N): "
                ):
                    return
                schedules = future_schedules
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        non_extendable = []
        for schedule in schedules:
            end_date = (
                schedule.end + timedelta(weeks=weeks) if weeks else datetime.strptime(date_arg, "%Y-%m-%d %H:%M")
            )
            data = {
                "start": ":".join(schedule.end.isoformat().split(":")[:-1]),
                "end": ":".join(end_date.isoformat().split(":")[:-1]),
            }
            try:
                is_host_available = self.quads.is_available(schedule.host.name, data)
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            if not is_host_available or end_date < schedule.end:
                non_extendable.append(schedule.host)

        if non_extendable:
            self.logger.warning(
                "The following hosts cannot be extended for the "
                "allocation or target date is sooner than current end date:"
            )
            for host in non_extendable:
                self.logger.info(host.name)
            return

        if not check:
            data = {
                "one_day": False,
                "three_days": False,
                "five_days": False,
                "seven_days": False,
            }
            try:
                self.quads.update_notification(schedules[0].assignment.notification.id, data)

                for schedule in schedules:
                    end_date = (
                        schedule.end + timedelta(weeks=weeks)
                        if weeks
                        else datetime.strptime(date_arg, "%Y-%m-%d %H:%M")
                    )
                    end = ":".join(end_date.isoformat().split(":")[:-1])
                    self.quads.update_schedule(schedule.id, {"end": end})

            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))

            if weeks:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} has now been extended for {str(weeks)} week[s] until {str(end_date)[:16]}"
                )
            else:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} has now been extended until {str(_date)[:16]}"
                )
        else:
            self.logger.info(
                f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} can be extended until {str(end_date)[:16]}"
            )

    def action_shrink(self):
        weeks = self.cli_args.get("weeks")
        now = self.cli_args.get("now")
        date_arg = self.cli_args.get("datearg")
        cloud_name = self.cli_args.get("cloud")
        host_name = self.cli_args.get("host")
        check = self.cli_args.get("check")

        _date = None
        end_date = None

        if not weeks and not now and not date_arg:
            raise CliException("Missing option. Need --weeks, --date or --now when using --shrink")

        if not cloud_name and not host_name:
            raise CliException("Missing option. At least one of either --host or --cloud is required")

        if weeks:
            try:
                weeks = int(weeks)
            except ValueError:
                raise CliException("The value of --weeks must be an integer")

        elif date_arg:
            _date = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M")
        elif now:
            _date = datetime.now()

        threshold = datetime.now() + timedelta(hours=1)

        dispatch = {"cloud": self.quads.get_cloud, "host": self.quads.get_host}
        dispatch_key = "cloud" if cloud_name else "host"
        data_dispatch = {"cloud": cloud_name} if cloud_name else {"host": host_name}

        try:
            dispatched_obj = dispatch[dispatch_key](data_dispatch[dispatch_key])
            if not dispatched_obj:  # pragma: no cover
                raise CliException(f"{dispatch_key.capitalize()} not found")

            schedules = self.quads.get_current_schedules(data_dispatch)
            if not schedules:
                self.logger.error(f"The selected {dispatch_key} does not have any active schedules")
                future_schedules = self.quads.get_future_schedules(data_dispatch)
                if not future_schedules:
                    return

                if not self._confirmation_dialog(
                    "Would you like to shrink a future allocation of" f" {data_dispatch[dispatch_key]}? (y/N): "
                ):
                    return
                schedules = future_schedules
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))

        non_shrinkable = []
        for schedule in schedules:
            end_date = schedule.end - timedelta(weeks=weeks) if weeks else _date
            if end_date < schedule.start or end_date > schedule.end or (not now and end_date < threshold):
                non_shrinkable.append(schedule.host)

        if non_shrinkable:
            self.logger.info(
                "The following hosts cannot be shrunk past it's start date, target date means an extension"
                " or target date is earlier than 1 hour from now:"
            )
            for host in non_shrinkable:
                self.logger.info(host.name)
            return

        if not check:
            confirm_msg = f"for {weeks} week[s]? (y/N): " if weeks else f"to {str(_date)[:16]}? (y/N): "
            if not self._confirmation_dialog(
                f"Are you sure you want to shrink {data_dispatch[dispatch_key]} " + confirm_msg
            ):
                return

            for schedule in schedules:
                end_date = schedule.end - timedelta(weeks=weeks) if weeks else _date
                end = ":".join(end_date.isoformat().split(":")[:-1])
                self.quads.update_schedule(schedule.id, {"end": end})

            if weeks:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} has now been shrunk for {str(weeks)} week[s] until {str(end_date)[:16]}"
                )
            elif date_arg:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} has now been shrunk until {str(_date)[:16]}"
                )
            else:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} has now been shrunk to {str(_date)[:16]}"
                )
        else:
            if weeks:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} can be shrunk for {str(weeks)} week[s] to {str(end_date)[:16]}"
                )
            elif date_arg:
                self.logger.info(
                    f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} can be shrunk to {str(end_date)[:16]}"
                )
            else:
                self.logger.info(f"{dispatch_key.capitalize()} {data_dispatch[dispatch_key]} can be terminated now")

    def action_cloudresource(self):
        assignment = None
        cloud = None
        data = {
            "cloud": self.cli_args.get("cloud"),
            "description": self.cli_args.get("description"),
            "owner": self.cli_args.get("cloudowner"),
            "ccuser": self.cli_args.get("ccusers"),
            "qinq": self.cli_args.get("qinq"),
            "ticket": self.cli_args.get("cloudticket"),
            "force": self.cli_args.get("force"),
            "wipe": self.cli_args.get("wipe", True),
        }
        if self.cli_args.get("vlan"):
            try:
                data["vlan"] = int(self.cli_args.get("vlan"))
            except (TypeError, ValueError) as ཀʖ̯ཀ:
                self.logger.debug(ཀʖ̯ཀ, exc_info=ཀʖ̯ཀ)
                raise CliException("Could not parse vlan id. Only integers accepted.")

        if self.cli_args.get("os"):
            os_type = self.cli_args.get("os")
            available_os = self.quads.get_os_list()
            if any(_os["Title"] == os_type for _os in available_os):
                data["ostype"] = os_type
            else:
                raise CliException(f"Could not parse os {os_type}, please check available os --os-list.")

        if not data.get("ostype"):
            data["ostype"] = conf["foreman_default_os"]

        if self.cli_args.get("boot_order"):
            boot_order = self.cli_args.get("boot_order")
            interfaces_path = conf.get("badfish_interfaces_path")
            loop = asyncio.get_event_loop()
            host_types = loop.run_until_complete(Badfish.get_host_types_from_yaml(interfaces_path))
            if boot_order in host_types:
                data["boot_order"] = boot_order
            else:
                raise CliException(f"Could not parse boot order {boot_order}, available boot orders: {host_types}")

        if not data.get("boot_order"):
            data["boot_order"] = conf["foreman_default_boot_order"]

        cloud_reservation_lock = int(conf["cloud_reservation_lock"])
        try:
            cloud = self.quads.get_cloud(self.cli_args.get("cloud"))
        except (APIServerException, APIBadRequest) as ex:
            self.logger.debug(ex, exc_info=ex)

        if cloud and cloud.name != conf.get("spare_pool_name"):
            try:
                assignment = self.quads.get_active_cloud_assignment(self.cli_args.get("cloud"))
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))

            if assignment:
                last_redefined = datetime.strptime(str(cloud.last_redefined), "%a, %d %b %Y %H:%M:%S GMT")
                lock_release = last_redefined + timedelta(hours=cloud_reservation_lock)
                cloud_string = f"{cloud.name}"
                if lock_release > datetime.now():
                    time_left = lock_release - datetime.now()
                    hours = time_left.total_seconds() // 3600
                    minutes = (time_left.total_seconds() % 3600) // 60
                    cloud_string += " (reserved: %dhr %dmin remaining)" % (
                        hours,
                        minutes,
                    )
                    self.logger.warning("Can't redefine cloud:")
                    self.logger.warning(cloud_string)
                    return 1

        try:
            if not cloud:
                try:
                    cloud_response = self.quads.insert_cloud(data)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))
                if cloud_response.status_code == 200:
                    self.logger.info(f'Cloud {self.cli_args.get("cloud")} created.')

            if (
                not assignment
                and self.cli_args.get("cloudticket")
                and self.cli_args.get("cloud") != conf.get("spare_pool_name")
            ):
                try:
                    response = self.quads.insert_assignment(data)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))
                if response.status_code == 200:
                    self.logger.info("Assignment created.")
                if cloud:
                    try:
                        self.quads.update_cloud(
                            cloud.name,
                            {"last_redefined": ":".join(datetime.now().isoformat().split(":")[:-1])},
                        )
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
            elif assignment:
                raise CliException("Cloud already has an active assignment.")
            else:
                if self.cli_args.get("cloud") != conf.get("spare_pool_name"):
                    if not self.cli_args.get("cloudticket"):
                        self.logger.warning("No ticket provided.")
                    self.logger.warning("No assignment created.")

        except ConnectionError:  # pragma: no cover
            raise CliException("Could not connect to the quads-server, verify service is up and running.")

    def action_modcloud(self):
        data = {
            "cloud": self.cli_args.get("cloud"),
            "description": self.cli_args.get("description"),
            "owner": self.cli_args.get("cloudowner"),
            "ccuser": self.cli_args.get("ccusers"),
            "ticket": self.cli_args.get("cloudticket"),
        }

        clean_data = {k: v for k, v in data.items() if v and k != "cloud"}
        if self.cli_args.get("vlan"):
            try:
                clean_data["vlan"] = int(self.cli_args.get("vlan"))
            except (TypeError, ValueError):  # pragma: no cover
                clean_data["vlan"] = "None"

        if self.cli_args.get("os"):
            os_type = self.cli_args.get("os")
            available_os = self.quads.get_os_list()
            if any(_os["Title"] == os_type for _os in available_os):
                clean_data["ostype"] = os_type
            else:
                raise CliException(f"Could not parse os {os_type}, please check available os --os-list.")

        if "wipe" in self.cli_args:
            clean_data["wipe"] = self.cli_args.get("wipe")
        if "qinq" in self.cli_args:
            clean_data["qinq"] = self.cli_args.get("qinq")

        try:
            assignment = self.quads.get_active_cloud_assignment(self.cli_args.get("cloud"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if not assignment:
            raise CliException(f"No active cloud assignment for {self.cli_args.get('cloud')}")

        try:
            self.quads.update_assignment(assignment.id, clean_data)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        self.logger.info("Cloud modified successfully")

    def action_rmcloud(self):
        cloud = self.cli_args.get("cloud")
        if not cloud:
            raise CliException("Missing parameter --cloud")

        try:
            assignment = self.quads.get_active_cloud_assignment(cloud)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        if assignment:
            raise CliException(f"There is an active cloud assignment for {cloud}")

        try:
            _response = self.quads.remove_cloud(self.cli_args.get("cloud"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        self._output_json_result(_response, {"cloud": self.cli_args.get("cloud")})

    def action_rmhost(self):
        if not self.cli_args.get("host"):
            raise CliException("Missing parameter --host")
        try:
            _response = self.quads.remove_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        self._output_json_result(_response, {"host": self.cli_args.get("host")})

    def action_hostresource(self):
        if not self.cli_args.get("host"):  # pragma: no cover
            raise CliException("Missing parameter --host")
        if not self.cli_args.get("defaultcloud"):
            raise CliException("Missing parameter --default-cloud")

        data = {
            "name": self.cli_args.get("host"),
            "default_cloud": self.cli_args.get("defaultcloud"),
            "host_type": self.cli_args.get("hosttype"),
            "model": self.cli_args.get("model"),
            "force": self.cli_args.get("force"),
            "rack": self.cli_args.get("rack"),
            "uloc": self.cli_args.get("uloc"),
            "blade": self.cli_args.get("blade"),
        }
        try:
            _host = self.quads.create_host(data)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        self.logger.info(f"{_host.name}")

    def action_modhost(self):
        data = {}
        hostname = self.cli_args.get("host")
        if not hostname:
            raise CliException("Missing parameter --host")
        try:
            self.quads.get_host(hostname)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if self.cli_args.get("cloud"):
            try:
                cloud = self.quads.get_cloud(self.cli_args.get("cloud"))
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            data["cloud"] = cloud.name

        if self.cli_args.get("defaultcloud"):
            try:
                cloud = self.quads.get_cloud(self.cli_args.get("defaultcloud"))
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            data["default_cloud"] = cloud.name

        data = {
            "name": hostname,
            "model": self.cli_args.get("model"),
            "host_type": self.cli_args.get("hosttype"),
            "build": self.cli_args.get("build"),
            "validated": self.cli_args.get("validated"),
            "switch_config_applied": self.cli_args.get("switchconfigapplied"),
            "can_self_schedule": self.cli_args.get("canselfschedule"),
        }

        try:
            response = self.quads.update_host(hostname, data)
            _json = response.json()
            for key in ["interfaces", "disks", "memory", "processors"]:
                _json.pop(key, None)
            yaml_str = yaml.dump(_json, default_flow_style=False, sort_keys=False)
            self.logger.info("\n" + yaml_str)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

    def prepare_host_data(self, metadata) -> dict:
        data = {}
        for key, value in metadata.items():
            if key != "default_cloud":
                if type(value) is not list:
                    data[key] = value

            elif key == "default_cloud":
                try:
                    cloud = self.quads.get_cloud(value)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))
                data[key] = cloud.name
        return data

    def action_define_host_metadata(self):
        dispatch_create = {
            "disks": self.quads.create_disk,
            "interfaces": self.quads.create_interface,
            "memory": self.quads.create_memory,
            "processors": self.quads.create_processor,
        }
        if not self.cli_args.get("metadata"):
            raise CliException("Missing option --metadata")

        if not os.path.exists(self.cli_args.get("metadata")):
            raise CliException("The path for the --metadata yaml is not valid")

        try:
            with open(self.cli_args.get("metadata")) as md:
                hosts_metadata = yaml.safe_load(md)
        except IOError as ಠ_ಠ:
            self.logger.debug(ಠ_ಠ, exc_info=ಠ_ಠ)
            raise CliException(f"There was something wrong reading from {self.cli_args['metadata']}")

        for host_md in hosts_metadata:
            ready_defined = []
            host = None
            try:
                host = self.quads.get_host(host_md.get("name"))
            except (APIServerException, APIBadRequest):  # pragma: no cover
                pass

            if not host:
                if self.cli_args.get("force"):
                    host_data = self.prepare_host_data(host_md)
                    try:
                        self.quads.create_host(host_data)
                        self.logger.info(f"{host_md.get('name')} created")
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
                else:
                    self.logger.warning(f"Host {host_md.get('name')} not found. Skipping.")
                    continue

            host = self.quads.get_host(host_md.get("name"))

            data = {}
            for key, value in host_md.items():
                if key != "name" and key != "default_cloud" and getattr(host, key) is not None:
                    ready_defined.append(key)
                    if not self.cli_args.get("force"):  # pragma: no cover
                        continue
                    if isinstance(value, list):
                        if host:
                            self.clear_field(host, key)
                        dispatch_func = dispatch_create.get(key)
                        for obj in value:
                            if dispatch_func:
                                try:
                                    dispatch_func(host.name, obj)
                                except (
                                    APIServerException,
                                    APIBadRequest,
                                ) as ex:  # pragma: no cover
                                    raise CliException(str(ex))
                            else:  # pragma: no cover
                                raise CliException(f"Invalid key '{key}' on metadata for {host.name}")
                    else:
                        data[key] = value

                elif key == "default_cloud":
                    try:
                        cloud = self.quads.get_cloud(value)
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
                    data[key] = cloud.name

            if ready_defined:
                action = "SKIPPING" if not self.cli_args.get("force") else "RECREATING"
                self.logger.warning(f"{host.name} [{action}]: {ready_defined}")

            if data and len(data.keys()) > 1:
                try:
                    self.quads.update_host(host.name, data)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))

        if not self.cli_args.get("force"):  # pragma: no cover
            self.logger.warning("For overwriting existing values use the --force.")

    def action_host_metadata_export(self):
        try:
            all_hosts = self.quads.get_hosts()
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        content = []
        for host in all_hosts:
            host_meta = {
                "name": host.name,
                "model": host.model,
                "host_type": host.host_type,
                "default_cloud": host.default_cloud.name,
                "broken": host.broken,
                "retired": host.retired,
            }

            interfaces = []
            for interface in host.interfaces:
                interface_dict = {
                    "name": interface.name,
                    "mac_address": interface.mac_address,
                    "switch_ip": interface.switch_ip,
                    "switch_port": interface.switch_port,
                    "speed": interface.speed if interface.speed else 0,
                    "vendor": interface.vendor,
                    "pxe_boot": interface.pxe_boot,
                    "maintenance": interface.maintenance,
                }
                interfaces.append(interface_dict)
            if interfaces:
                host_meta["interfaces"] = interfaces

            disks = []
            for disk in host.disks:
                if disk.size_gb > 0:
                    disk_dict = {
                        "disk_type": disk.disk_type,
                        "size_gb": disk.size_gb,
                        "count": disk.count,
                    }
                    disks.append(disk_dict)
            if disks:
                host_meta["disks"] = disks

            memories = []
            for memory in host.memory:
                memory_dict = {
                    "handle": memory.handle,
                    "size_gb": memory.size_gb,
                }
                memories.append(memory_dict)
            if memories:
                host_meta["memory"] = memories

            processors = []
            for processor in host.processors:
                processor_dict = {
                    "handle": processor.handle,
                    "vendor": processor.vendor,
                    "product": processor.product,
                    "cores": processor.cores,
                    "threads": processor.threads,
                }
                processors.append(processor_dict)
            if processors:
                host_meta["processors"] = processors

            content.append(host_meta)

        try:
            with NamedTemporaryFile("w", delete=False) as temp:
                yaml.dump(content, temp)
                self.logger.info(f"Metadata successfully exported to {temp.name}.")
        except Exception as ಠ益ಠ:  # pragma: no cover
            self.logger.debug(ಠ益ಠ, exc_info=ಠ益ಠ)
            raise BaseQuadsException("There was something wrong writing to file.") from ಠ益ಠ

        return 0

    def action_add_schedule(self):
        if (
            self.cli_args.get("schedstart") is None
            or self.cli_args.get("schedend") is None
            or self.cli_args.get("schedcloud") is None
        ):
            raise CliException(
                "Missing option. All of these options are required for --add-schedule:\n"
                "\t--schedule-start\n"
                "\t--schedule-end\n"
                "\t--schedule-cloud"
            )

        if not self.cli_args.get("host") and not self.cli_args.get("host_list"):
            raise CliException("Missing option. --host or --host-list required.")

        if self.cli_args.get("omitcloud"):
            try:
                self.quads.get_cloud(self.cli_args.get("omitcloud"))
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))

        if self.cli_args.get("host"):
            if self.cli_args.get("omitcloud"):
                try:
                    host = self.quads.get_host(self.cli_args.get("host"))
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))
                if host.cloud.name == self.cli_args.get("omitcloud"):
                    self.logger.info(
                        "Host is in part of the cloud specified with --omit-cloud. Nothing has been done."
                    )
            else:
                data = {
                    "cloud": self.cli_args.get("schedcloud"),
                    "hostname": self.cli_args.get("host"),
                    "start": self.cli_args.get("schedstart"),
                    "end": self.cli_args.get("schedend"),
                }
                try:
                    self.quads.insert_schedule(data)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))
                self.logger.info("Schedule created")

        elif self.cli_args.get("host_list"):
            try:
                with open(self.cli_args.get("host_list")) as _file:
                    host_list_stream = _file.read()
            except IOError:
                raise CliException(f"Could not read file: {self.cli_args['host_list']}.")

            host_list = host_list_stream.split()
            non_available = []
            _sched_start = datetime.strptime(self.cli_args.get("schedstart"), "%Y-%m-%d %H:%M")
            _sched_end = datetime.strptime(self.cli_args.get("schedend"), "%Y-%m-%d %H:%M")

            if self.cli_args.get("omitcloud"):
                self.logger.info(f"INFO - All hosts from {self.cli_args['omitcloud']} will be omitted.")
                omitted = []

                for host in host_list:
                    try:
                        host_obj = self.quads.get_host(host)
                    except (APIServerException, APIBadRequest) as ex:
                        raise CliException(str(ex))
                    if host_obj.cloud.name == self.cli_args.get("omitcloud"):
                        omitted.append(host)
                for host in omitted:
                    host_list.remove(host)
                    self.logger.info(f"{host} will be omitted.")

            for host in host_list:
                try:
                    is_available = self.quads.is_available(
                        hostname=host,
                        data={
                            "start": _sched_start.isoformat()[:-3],
                            "end": _sched_end.isoformat()[:-3],
                        },
                    )
                    host_obj = self.quads.get_host(host)
                    if not is_available or host_obj.broken:
                        non_available.append(host)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    raise CliException(str(ex))

            if non_available:
                self.logger.error("The following hosts are either broken or unavailable:")

                for host in non_available:
                    self.logger.error(host)
                raise CliException("Remove these from your host list and try again.")

            for host in host_list:
                data = {
                    "cloud": self.cli_args.get("schedcloud"),
                    "hostname": host,
                    "start": self.cli_args.get("schedstart"),
                    "end": self.cli_args.get("schedend"),
                }
                try:
                    try:
                        self.quads.insert_schedule(data)
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
                    self.logger.info(f"Schedule created for {host}")
                except ConnectionError:
                    raise CliException("Could not connect to the quads-server, verify service is up and running.")

            template_file = "jira_ticket_assignment"
            with open(os.path.join(conf.TEMPLATES_PATH, template_file)) as _file:
                template = Template(_file.read())

            try:
                self.quads.get_cloud(self.cli_args.get("schedcloud"))
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            jira_docs_links = conf["jira_docs_links"].split(",")
            jira_vlans_docs_links = conf["jira_vlans_docs_links"].split(",")
            ass = self.quads.get_active_cloud_assignment(self.cli_args.get("schedcloud"))
            comment = template.render(
                schedule_start=self.cli_args.get("schedstart"),
                schedule_end=self.cli_args.get("schedend"),
                cloud=self.cli_args.get("schedcloud"),
                jira_docs_links=jira_docs_links,
                jira_vlans_docs_links=jira_vlans_docs_links,
                host_list=host_list_stream,
                vlan=ass.vlan,
            )

            loop = asyncio.get_event_loop()
            try:
                jira = Jira(
                    conf["jira_url"],
                    loop=loop,
                )
            except JiraException as ex:  # pragma: no cover
                self.logger.error(ex)
                exit(1)
            result = loop.run_until_complete(jira.post_comment(ass.ticket, comment))
            if not result:
                self.logger.warning("Failed to update Jira ticket")

            transitions = loop.run_until_complete(jira.get_transitions(ass.ticket))
            transition_result = False
            for transition in transitions:
                t_name = transition.get("name")
                if t_name and t_name.lower() == "scheduled":
                    transition_id = transition.get("id")
                    transition_result = loop.run_until_complete(jira.post_transition(ass.ticket, transition_id))
                    break

            if not transition_result:
                self.logger.warning("Failed to update ticket status")

        return 0

    def action_rmschedule(self):
        if self.cli_args.get("schedid") is None:
            raise CliException("Missing option --schedule-id.")

        try:
            self.logger.info(self.quads.remove_schedule(self.cli_args.get("schedid")))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        return 0

    def action_modschedule(self):
        if not self.cli_args.get("schedstart") and not self.cli_args.get("schedend"):
            raise CliException(
                "Missing option. At least one these options are required for --mod-schedule:\n"
                "\t--schedule-start\n"
                "\t--schedule-end"
            )

        mapping = {
            "start": "schedstart",
            "end": "schedend",
            "hostname": "host",
        }
        data = {}
        for k, v in mapping.items():
            value = self.cli_args.get(v)
            if value:
                if k in ["start", "end"]:
                    value = ":".join(datetime.strptime(value, "%Y-%m-%d %H:%M").isoformat().split(":")[:-1])
                data[k] = value
        try:
            schedule = self.quads.get_schedule(self.cli_args.get("schedid"))
            self.quads.update_schedule(self.cli_args.get("schedid"), data)
            not_data = {
                "one_day": False,
                "three_day": False,
                "five_day": False,
                "seven_day": False,
                "pre": False,
            }
            self.quads.update_notification(schedule.assignment["notification"]["id"], not_data)
            self.logger.info("Schedule updated successfully.")
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        return 0

    def action_addinterface(self):
        _ifmac = self.cli_args.get("ifmac", None)
        _ifname = self.cli_args.get("ifname", None)
        _ifip = self.cli_args.get("ifip", None)
        _ifport = self.cli_args.get("ifport", None)
        _ifpxe = self.cli_args.get("ifpxe", False)
        _ifbiosid = self.cli_args.get("ifbiosid", None)
        _ifspeed = self.cli_args.get("ifspeed", None)
        _ifvendor = self.cli_args.get("ifvendor", None)
        _ifmaintenance = self.cli_args.get("ifmaintenance", False)
        _force = self.cli_args.get("force", None)
        _host = self.cli_args.get("host", None)
        if _ifmac is None or _ifname is None or _ifip is None or _ifport is None or _ifport is None:
            raise CliException(
                "Missing option. All these options are required for --add-interface:\n"
                "\t--host\n"
                "\t--interface-name\n"
                "\t--interface-mac\n"
                "\t--interface-ip\n"
                "\t--interface-port"
            )

        default_interface = conf.get("default_pxe_interface")
        if default_interface and _ifname == default_interface:
            pxe_boot = True
        else:
            pxe_boot = _ifpxe

        data = {
            "name": _ifname,
            "bios_id": _ifbiosid,
            "mac_address": _ifmac,
            "switch_ip": _ifip,
            "switch_port": _ifport,
            "speed": _ifspeed,
            "vendor": _ifvendor,
            "maintenance": _ifmaintenance,
            "pxe_boot": pxe_boot,
            "force": _force,
        }

        try:
            self.quads.create_interface(_host, data)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        return 0

    def action_rminterface(self):
        if not self.cli_args.get("host") or not self.cli_args.get("ifname"):
            raise CliException("Missing option. --host and --interface-name options are required for --rm-interface")

        data = {
            "hostname": self.cli_args.get("host"),
            "if_name": self.cli_args.get("ifname"),
        }
        try:
            self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        try:
            response = self.quads.remove_interface(**data)
            self.logger.info(response)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        return 0

    def action_modinterface(self):
        fields_map = {
            "ifmac": "mac_address",
            "ifip": "switch_ip",
            "ifport": "switch_port",
            "ifpxe": "pxe_boot",
            "ifbiosid": "bios_id",
            "ifspeed": "speed",
            "ifvendor": "vendor",
            "ifmaintenance": "maintenance",
        }
        _ifmac = self.cli_args.get("ifmac", None)
        _ifname = self.cli_args.get("ifname", None)
        _ifip = self.cli_args.get("ifip", None)
        _ifport = self.cli_args.get("ifport", None)
        _ifbiosid = self.cli_args.get("ifbiosid", None)
        _ifspeed = self.cli_args.get("ifspeed", None)
        _ifvendor = self.cli_args.get("ifvendor", None)
        _host = self.cli_args.get("host", None)
        # TODO: fix all
        if _host is None or _ifname is None:
            raise CliException("Missing option. --host and --interface-name options are required for --mod-interface:")

        try:
            host = self.quads.get_host(_host)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        mod_interface = None
        for interface in host.interfaces:
            if interface.name.lower() == self.cli_args.get("ifname").lower():
                mod_interface = interface

        if not mod_interface:
            self.logger.error("Interface not found")
            return 1

        if (
            _ifbiosid is None
            and _ifmac is None
            and _ifip is None
            and _ifport is None
            and _ifspeed is None
            and _ifvendor is None
            and not hasattr(self.cli_args, "ifpxe")
            and not hasattr(self.cli_args, "ifmaintenance")
        ):
            raise CliException(
                "Missing options. At least one of these options are required for --mod-interface:\n"
                "\t--interface-name\n"
                "\t--interface-bios-id\n"
                "\t--interface-mac\n"
                "\t--interface-ip\n"
                "\t--interface-port\n"
                "\t--interface-speed\n"
                "\t--interface-vendor\n"
                "\t--pxe-boot\n"
                "\t--maintenance"
            )

        data = {"id": mod_interface.id}

        for arg, key in fields_map.items():
            if arg in self.cli_args and self.cli_args is not None:
                data[key] = self.cli_args[arg]

        try:
            self.quads.update_interface(self.cli_args.get("host"), data)
            self.logger.info("Interface successfully updated")
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            self.logger.error("Failed to update interface")
            raise CliException(str(ex))
        return 0

    def action_movehosts(self):  # pragma: no cover
        if self.cli_args.get("datearg") and not self.cli_args.get("dryrun"):
            raise CliException("--move-hosts and --date are mutually exclusive unless using --dry-run.")

        date = ""
        if self.cli_args.get("datearg"):
            date = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M").isoformat()[:-3]

        try:
            moves = self.quads.get_moves(date)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if not moves:
            self.logger.info("Nothing to do.")
            return 0

        if moves:
            _clouds = defaultdict(list)
            for result in moves:
                _clouds[result["new"]].append(result)

            # TODO:
            #  raise the number of semaphores after this is resolved
            #  https://projects.theforeman.org/issues/27953#change-127120
            semaphore = asyncio.Semaphore(1)
            for _cloud, results in _clouds.items():
                provisioned = True
                tasks = []
                switch_tasks = []
                for result in results:
                    host = result["host"]
                    current = result["current"]
                    new = result["new"]
                    try:
                        cloud = self.quads.get_cloud(new)
                        assignment = self.quads.get_active_cloud_assignment(cloud.name)
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))
                    target_assignment = None
                    if assignment:
                        target_assignment = Assignment().from_dict(data=assignment)
                    wipe = target_assignment.wipe if target_assignment else False

                    self.logger.info(f"Moving {host} from {current} to {new}, wipe = {wipe}")
                    if not self.cli_args.get("dryrun"):
                        try:
                            self.quads.update_host(
                                host,
                                {
                                    "switch_config_applied": False,
                                    "provisioned": False,
                                    "build": False,
                                },
                            )
                        except (
                            APIServerException,
                            APIBadRequest,
                        ) as ex:  # pragma: no cover
                            raise CliException(str(ex))
                        if new != "cloud01":
                            try:
                                has_active_schedule = self.quads.get_current_schedules({"cloud": f"{cloud.name}"})
                                if has_active_schedule and wipe:
                                    assignment = self.quads.get_active_cloud_assignment(cloud.name)
                                    self.quads.update_assignment(assignment.id, {"validated": False})
                            except (
                                APIServerException,
                                APIBadRequest,
                            ) as ex:  # pragma: no cover
                                raise CliException(str(ex))
                        try:
                            if self.cli_args.get("movecommand") == default_move_command:
                                fn = functools.partial(move_and_rebuild, host, new, semaphore, wipe)
                                tasks.append(fn)
                                omits = conf.get("omit_network_move")
                                omit = False
                                if omits:
                                    omits = omits.split(",")
                                    omit = [omit for omit in omits if omit in host or omit == new]
                                if not omit:
                                    switch_tasks.append(functools.partial(switch_config, host, current, new))
                            else:
                                if wipe:
                                    subprocess.check_call(
                                        [
                                            self.cli_args.get("movecommand"),
                                            host,
                                            current,
                                            new,
                                        ]
                                    )
                                else:
                                    subprocess.check_call(
                                        [
                                            self.cli_args.get("movecommand"),
                                            host,
                                            current,
                                            new,
                                            "nowipe",
                                        ]
                                    )
                        except Exception as ex:
                            self.logger.debug(ex)
                            self.logger.exception("Move command failed for host: %s" % host)
                            provisioned = False

                if not self.cli_args.get("dryrun"):
                    try:
                        old_clouds = set()
                        for result in results:
                            old_clouds.add(result["current"])
                        for old_cloud in old_clouds:
                            _old_cloud_obj = self.quads.get_cloud(old_cloud)
                            old_cloud_schedule = self.quads.get_current_schedules({"cloud": _old_cloud_obj.name})

                            if not old_cloud_schedule and _old_cloud_obj.name != "cloud01":
                                _old_ass_cloud_obj = self.quads.get_active_cloud_assignment(_old_cloud_obj.name)
                                if _old_ass_cloud_obj:
                                    payload = {"active": False}
                                    self.quads.update_assignment(_old_ass_cloud_obj.id, payload)
                    except (
                        APIServerException,
                        APIBadRequest,
                    ) as ex:  # pragma: no cover
                        raise CliException(str(ex))

                    done = None
                    loop = asyncio.get_event_loop()
                    loop.set_exception_handler(
                        lambda _loop, ctx: self.logger.error(f"Caught exception: {ctx['message']}")
                    )

                    try:
                        done = loop.run_until_complete(asyncio.gather(*[task(loop) for task in tasks]))
                    except (
                        asyncio.CancelledError,
                        SystemExit,
                        Exception,
                        TimeoutError,
                    ):
                        self.logger.exception("Move command failed")
                        provisioned = False
                    for task in switch_tasks:
                        try:
                            host_obj = self.quads.get_host(task.args[0])
                        except (
                            APIServerException,
                            APIBadRequest,
                        ) as ex:  # pragma: no cover
                            self.logger.exception(str(ex))
                            continue

                        if not host_obj.switch_config_applied:
                            self.logger.info(f"Running switch config for {task.args[0]}")

                            try:
                                result = task()
                            except Exception as exc:
                                self.logger.exception(
                                    "There was something wrong configuring the switch.",
                                    exc_info=exc,
                                )

                            if result:
                                try:
                                    self.quads.update_host(task.args[0], {"switch_config_applied": True})
                                except (
                                    APIServerException,
                                    APIBadRequest,
                                ) as ex:  # pragma: no cover
                                    self.logger.exception(str(ex))
                                    continue
                            else:
                                self.logger.exception("There was something wrong configuring the switch.")

                    if done:
                        for future in done:
                            if isinstance(future, Exception):
                                provisioned = False
                            else:
                                provisioned = provisioned and future

                    if provisioned:
                        try:
                            _new_cloud_obj = self.quads.get_cloud(_cloud)
                            assignment = self.quads.get_active_cloud_assignment(_new_cloud_obj.name)
                            if assignment:
                                validate = not assignment.wipe
                                self.quads.update_assignment(
                                    assignment.id,
                                    {"provisioned": True, "validated": validate},
                                )
                                foreman_heal(self.logger)
                        except (
                            APIServerException,
                            APIBadRequest,
                        ) as ex:  # pragma: no cover
                            raise CliException(str(ex))

            return 0

    def action_mark_broken(self):
        if not self.cli_args.get("host"):
            raise CliException("Missing option. Need --host when using --mark-broken")

        try:
            host = self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if host.broken:
            self.logger.warning(f"Host {self.cli_args['host']} has already been marked broken")
        else:
            try:
                self.quads.update_host(self.cli_args.get("host"), {"broken": True})
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            self.logger.info(f"Host {self.cli_args['host']} is now marked as broken")

    def action_mark_repaired(self):
        if not self.cli_args.get("host"):
            raise CliException("Missing option. Need --host when using --mark-repaired")

        try:
            host = self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if not host.broken:
            self.logger.warning(f"Host {self.cli_args['host']} has already been marked repaired")
        else:
            try:
                self.quads.update_host(self.cli_args.get("host"), {"broken": False})
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            self.logger.info(f"Host {self.cli_args['host']} is now marked as repaired")

    def action_retire(self):
        if not self.cli_args.get("host"):
            raise CliException("Missing option. Need --host when using --retire")

        try:
            host = self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if host.retired:
            self.logger.warning(f"Host {self.cli_args['host']} has already been marked as retired")
        else:
            try:
                self.quads.update_host(self.cli_args.get("host"), {"retired": True})
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            self.logger.info(f"Host {self.cli_args['host']} is now marked as retired")

    def action_unretire(self):
        if not self.cli_args.get("host"):
            raise CliException("Missing option. Need --host when using --unretire")

        try:
            host = self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        if not host.retired:
            self.logger.warning(f"Host {self.cli_args['host']} has already been marked unretired")
        else:
            try:
                self.quads.update_host(self.cli_args.get("host"), {"retired": False})
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                raise CliException(str(ex))
            self.logger.info(f"Host {self.cli_args['host']} is now marked as unretired")

    def action_host(self):
        try:
            host = self.quads.get_host(self.cli_args.get("host"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        _kwargs = {"host": host.name}
        if self.cli_args.get("datearg"):
            datetime_obj = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M")
            datearg_iso = datetime_obj.isoformat()
            date_str = ":".join(datearg_iso.split(":")[:-1])
            _kwargs["date"] = date_str
        else:
            datetime_obj = datetime.now()
        schedules = self.quads.get_current_schedules(_kwargs)
        if schedules:
            for schedule in schedules:
                if schedule.end != datetime_obj:
                    self.logger.info(schedule.assignment.cloud.name)
        else:
            self.logger.info(host.default_cloud.name)

    def action_cloudonly(self):
        try:
            _cloud = self.quads.get_cloud(self.cli_args.get("cloud"))
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))

        _kwargs = {"cloud": _cloud.name}
        if self.cli_args.get("datearg"):
            _kwargs["date"] = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M").isoformat()[:-3]
        schedules = self.quads.get_current_schedules(_kwargs)
        if schedules:
            host_kwargs = {"retired": False}
            if self.cli_args.get("filter"):
                filter_args = self._filter_kwargs(self.cli_args.get("filter"))
                host_kwargs.update(filter_args)
            _hosts = self.quads.filter_hosts(host_kwargs)
            if _hosts:
                for schedule in sorted(schedules, key=lambda k: k.host.name):
                    if schedule.host.name in [host.name for host in _hosts]:
                        self.logger.info(schedule.host.name)
        else:
            if _kwargs.get("date") and self.cli_args.get("cloudonly") == "cloud01":
                data = {
                    "start": _kwargs["date"],
                    "end": _kwargs["date"],
                }

                try:
                    available_hosts = self.quads.filter_available(data)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    self.logger.debug(str(ex))
                    raise CliException("Could not connect to the quads-server, verify service is up and running.")

                host_kwargs = {}
                if self.cli_args.get("filter"):
                    filter_args = self._filter_kwargs(self.cli_args.get("filter"))
                    host_kwargs.update(filter_args)
                    _hosts = self.quads.filter_hosts(host_kwargs)
                else:
                    _hosts = self.quads.get_hosts()
                for host in sorted(_hosts, key=lambda k: k.name):
                    _hosts.append(host.name)
                for host in sorted(available_hosts):
                    if host in _hosts:
                        self.logger.info(host)
            else:
                host_kwargs = {"cloud": _cloud.name}
                if self.cli_args.get("filter"):
                    filter_args = self._filter_kwargs(self.cli_args.get("filter"))
                    host_kwargs.update(filter_args)
                _hosts = self.quads.filter_hosts(host_kwargs)
                if _hosts:
                    for host in sorted(_hosts, key=lambda k: k.name):
                        self.logger.info(host.name)

    def action_summary(self):
        _kwargs = {}
        if self.cli_args.get("datearg"):
            datearg_obj = datetime.strptime(self.cli_args.get("datearg"), "%Y-%m-%d %H:%M")
            datearg_iso = datearg_obj.isoformat()
            date_str = ":".join(datearg_iso.split(":")[:-1])
            _kwargs["date"] = date_str
        try:
            summary = self.quads.get_summary(_kwargs)
        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
            raise CliException(str(ex))
        summary_json = summary.json()
        for cloud in summary_json:
            cloud_name = cloud.get("name")
            cloud_count = cloud.get("count")
            cloud_description = cloud.get("description")
            cloud_owner = cloud.get("owner")
            cloud_ticket = cloud.get("ticket")
            if self.cli_args.get("all") or cloud["count"] > 0:
                if self.cli_args.get("detail"):
                    self.logger.info(
                        f"{cloud_name} ({cloud_owner}): {cloud_count} ({cloud_description}) - {cloud_ticket}"
                    )
                else:
                    self.logger.info(f"{cloud_name}: {cloud_count} ({cloud_description})")

    def action_regen_instack(self):
        regen_instack()
        if conf["openstack_management"]:
            self.logger.info("Regenerated 'instackenv' for OpenStack Management.")
        if conf["openshift_management"]:
            self.logger.info("Regenerated 'ocpinventory' for OpenShift Management.")

    def action_regen_heatmap(self):
        asyncio.run(regen_heatmap())
        self.logger.info("Regenerated web table heatmap.")

    def action_foreman_rbac(self):  # pragma: no cover
        foreman_heal(self.logger)
        self.logger.info("Foreman RBAC repaired.")

    def action_notify(self):
        notify(self.logger)
        self.logger.info("Notifications sent out.")

    def action_validate_env(self):
        _args = {
            "cloud": self.cli_args.get("cloud"),
            "skip_system": self.cli_args.get("skip_system"),
            "skip_network": self.cli_args.get("skip_network"),
            "skip_hosts": self.cli_args.get("skip_hosts"),
        }
        _loop = asyncio.get_event_loop()
        if _loop.is_closed():
            _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

        _loop.run_until_complete(validate_env(_args, self.logger))
        self.logger.info("Quads assignments validation executed.")

    def action_list_notifications(self):
        cloud_name = self.cli_args.get("cloud")
        try:
            if not cloud_name:
                assignments = self.quads.get_active_assignments()
            else:
                assignment = self.quads.get_active_cloud_assignment(cloud_name=cloud_name)
                assignments = [] if not assignment else [assignment]
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        headers = [
            "fail",
            "success",
            "initial",
            "pre_initial",
            "pre",
            "one_day",
            "three_days",
            "five_days",
            "seven_days",
        ]
        rows = []
        if assignments:
            for ass in assignments:
                cloud_name = str(ass.cloud.name)
                ticket = str(ass.ticket)
                notification = ass.notification
                row = [cloud_name, ticket]
                for header in headers:
                    row.append(str(getattr(notification, header)))
                rows.append(row)
            headers.insert(0, "cloud")
            headers.insert(1, "ticket")
            self.log_in_table_format(headers=headers, rows=rows)
        else:
            message = "WARNING: there are no current or future schedules"
            if not cloud_name:
                self.logger.warning(f"{message}")
            else:
                self.logger.warning(f"{message} for {cloud_name}")

    def action_modify_notification(self):
        cloud_name = self.cli_args.get("cloud")
        if not cloud_name:
            raise CliException("Missing parameter --cloud")
        mod_notification_arg_names = [
            "fail",
            "success",
            "initial",
            "pre_initial",
            "pre",
            "one_day",
            "three_days",
            "five_days",
            "seven_days",
        ]
        modify_notifications = list(
            filter(lambda item: self.cli_args.get(item) is not None, mod_notification_arg_names)
        )
        if not modify_notifications:
            err_message = ""
            for arg in mod_notification_arg_names:
                err_message += f"\n--{arg.replace('_', '-')} [true|false]"
            raise CliException("At least one arg should be given: {}".format(err_message))
        try:
            assignment = self.quads.get_active_cloud_assignment(cloud_name=cloud_name)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(str(ex))
        if assignment:
            assignment_id = assignment.id
            payload = {}
            for arg in modify_notifications:
                payload.update({arg: self.cli_args.get(arg)})
            response = self.quads.update_notification(notification_id=assignment_id, data=payload)
            if response.status_code == 200:
                self.logger.info(f"{cloud_name}, Notification updated successfully\n")
                self.action_list_notifications()
            else:
                self.logger.error("Something went wrong while updating notification")
        else:
            self.logger.warning(f"{cloud_name}, No active cloud assignment found")

    def log_in_table_format(self, headers: list, rows: list):
        col_widths = [max(len(str(item)) for item in col) for col in zip(headers, *rows)]

        def format_row(data_row):
            return "  ".join(str(item).ljust(width) for item, width in zip(data_row, col_widths))

        table = [format_row(headers), "=" * (sum(col_widths) + 2 * (len(headers) - 1))]
        table.extend(format_row(row) for row in rows)
        self.logger.info("\n".join(table))

    def action_os_list(self):
        available_os_list = self.quads.get_os_list()
        if available_os_list:
            headers = list(available_os_list[0].keys())
            rows = list(map(lambda item: list(item.values()), available_os_list))
            self.log_in_table_format(headers=headers, rows=rows)
        else:
            self.logger.error("No available OS list")
