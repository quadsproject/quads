#!/usr/bin/env python3
import argparse
import asyncio
import os
import random
from datetime import datetime
from typing import List
from urllib import parse as url_parse

import aiohttp
from aiohttp import BasicAuth
from jinja2 import Template
from requests import Response

from quads.config import Config
from quads.helpers.utils import first_day_month
from quads.server.models import Schedule, Host


class QuadsApiAsync:

    def __init__(self, config):
        self.config = config
        self.base_url = config.API_URL

    async def async_get(self, endpoint: str) -> Response:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    os.path.join(self.base_url, endpoint),
                    auth=BasicAuth(self.config.get("quads_api_username"), self.config.get("quads_api_password")),
                    timeout=60,
                    verify_ssl=False,
                ) as response:
                    result = await response.json()
        except Exception:
            result = {}
        return result

    async def get_monthly_schedules(self, start: datetime, end: datetime) -> List[Schedule]:
        endpoint = os.path.join("schedules", "hosts_range")
        url = f"{endpoint}"
        data = {
            "start": start.strftime("%Y-%m-%dT22:00"),
            "end": end.strftime("%Y-%m-%dT22:00"),
        }
        url_params = url_parse.urlencode(data)
        url = f"{endpoint}?{url_params}"
        schedules = await self.async_get(url)
        return schedules

    async def get_current_schedules(self) -> List[Schedule]:
        endpoint = os.path.join("schedules/current")
        url = f"{endpoint}"
        schedules = await self.async_get(url)
        return schedules

    async def async_filter_hosts(self, data) -> List[Host]:
        url_params = url_parse.urlencode(data)
        response = await self.async_get(f"hosts?{url_params}")
        hosts = []
        for host in response:
            host_obj = Host().from_dict(data=host)
            hosts.append(host_obj)
        return hosts


class HostGenerate:
    def __init__(self):
        self.hosts = []
        self.total_current_schedules = {}
        self.quads_async = QuadsApiAsync(Config)
        self.colors = []
        self.emojis = []
        self.current_host_schedules = {}
        self.assignment_colors = {}
        self.generate_colors()

    def random_color(self):
        def rand():
            return random.randint(100, 255)

        return "#%02X%02X%02X" % (rand(), rand(), rand())

    def generate_colors(self):
        all_samples = []
        all_samples.extend(range(129296, 129510))
        all_samples.extend(range(128000, 128252))
        samples = random.sample(all_samples, 200)
        exclude = [129401, 129484]
        self.emojis = [emoji for emoji in samples if emoji not in exclude]
        self.colors = [self.random_color() for _ in range(100)]
        self.colors[0] = "#A9A9A9"

    async def process_hosts(self, host, _days, _month, _year):
        allocated_count = 0
        __days = []
        schedules = self.total_current_schedules.get(host.name, [])
        for j in range(1, _days + 1):
            cell_date = "%s-%.2d-%.2d 01:00" % (_year, _month, j)
            cell_time = datetime.strptime(cell_date, "%Y-%m-%d %H:%M")
            _day = {
                "day": j,
                "cloud": "cloud01",
                "color": self.colors[0],
                "cell_date": cell_date,
                "cell_time": cell_time,
            }
            if schedules:
                for schedule in schedules:
                    if schedule.get("assignment_id") not in self.assignment_colors:
                        self.assignment_colors[schedule.get("assignment_id")] = len(self.assignment_colors) + 1
                    chosen_color = self.assignment_colors[schedule.get("assignment_id")]
                    schedule_start_date = datetime.strptime(schedule.get("start").split(".")[0], "%Y-%m-%dT%H:%M:%S")
                    schedule_end_date = datetime.strptime(schedule.get("end").split(".")[0], "%Y-%m-%dT%H:%M:%S")
                    if schedule_start_date <= cell_time <= schedule_end_date:
                        _day["display_description"] = schedule.get("description")
                        _day["display_owner"] = schedule.get("owner")
                        _day["display_ticket"] = schedule.get("ticket")
                        _day["cloud"] = schedule.get("cloud")
                        _day["emoji"] = "&#%s;" % self.emojis[chosen_color]
                        _day["color"] = self.colors[chosen_color]
                        allocated_count += 1
                        break
            __days.append(_day)
        return __days, allocated_count

    async def generator(self, _days, _month, _year, _gentime):
        self.hosts = await self.quads_async.async_filter_hosts(data={"retired": False, "broken": False})
        last_day = datetime(_year, _month, _days)
        first_day = first_day_month(last_day)
        self.total_current_schedules = await self.quads_async.get_monthly_schedules(first_day, last_day)
        current_schedules_today = await self.quads_async.get_current_schedules()

        lines = []
        allocated_count = 0

        for host in self.hosts:
            days, allocated = await self.process_hosts(host, _days, _month, _year)
            lines.append({"hostname": host.name, "days": days})
            allocated_count += allocated

        total_hosts = len(self.hosts)
        total_use = len(current_schedules_today)
        if int(total_hosts) == 0:
            utilization_daily = 0
            utilization = 0
        else:
            utilization = allocated_count * 100 // (_days * total_hosts)
            utilization_daily = total_use * 100 // total_hosts
        with open(os.path.join(Config.TEMPLATES_PATH, "simple_table_emoji")) as _file:
            template = Template(_file.read())
        content = template.render(
            gentime=_gentime,
            _days=_days,
            lines=lines,
            utilization=utilization,
            utilization_daily=utilization_daily,
            total_use=total_use,
            total_hosts=total_hosts,
        )

        return content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a simple HTML table with color depicting resource usage for the month"
    )
    requiredArgs = parser.add_argument_group("Required Arguments")
    requiredArgs.add_argument(
        "-d",
        "--days",
        dest="days",
        type=int,
        required=True,
        default=None,
        help="number of days to generate",
    )
    requiredArgs.add_argument(
        "-m",
        "--month",
        dest="month",
        type=str,
        required=True,
        default=None,
        help="Month to generate",
    )
    requiredArgs.add_argument(
        "-y",
        "--year",
        dest="year",
        type=str,
        required=True,
        default=None,
        help="Year to generate",
    )
    parser.add_argument(
        "--gentime",
        "-g",
        dest="gentime",
        type=str,
        required=False,
        default=None,
        help="generate timestamp when created",
    )

    args = parser.parse_args()
    days = args.days
    month = args.month
    year = args.year
    gentime = args.gentime

    generate = HostGenerate()
    asyncio.run(generate.generator(days, month, year, gentime))
