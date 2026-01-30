#!/usr/bin/env python3
import asyncio
import logging
import os
import sys

from datetime import timedelta
from jinja2 import Template
from quads.config import Config
from quads.quads_api import QuadsApi

from quads.tools.external.jira import Jira, JiraException
from quads.tools.external.postman import Postman
from quads.tools.helpers import get_or_create_event_loop

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

quads = QuadsApi(Config)


async def main(_loop):
    no_extend_label = "CANNOT_EXTEND"
    extend_label = "CAN_EXTEND"

    try:
        jira = Jira(
            Config["jira_url"],
            loop=_loop,
        )
    except JiraException as ex:
        logger.error(ex)
        return 1

    tickets = await jira.get_pending_tickets()
    for ticket in tickets["issues"]:
        ticket_key = ticket.get("key").split("-")[-1]
        fields = ticket.get("fields")
        if fields:
            description = fields.get("description")
            try:
                cloud_field = description.split("\n")[1]
                cloud = cloud_field.split()[-1]
            except IndexError:
                logger.warning(f"Could not retrieve cloud name from ticket {ticket_key}")
                continue

            if "EXTENSION" in fields.get("labels"):
                schedules = quads.get_current_schedules({"cloud": cloud})
                conflict = False
                for schedule in schedules:
                    end_date = schedule.end + timedelta(weeks=2)
                    data = {
                        "start": schedule.end.strftime("%Y-%m-%dT%H:%M"),
                        "end": end_date.strftime("%Y-%m-%dT%H:%M"),
                    }
                    available = quads.is_available(schedule.host.name, data)
                    if not available:
                        conflict = True
                        await jira.add_label(ticket_key, no_extend_label)
                        logger.info(f"{cloud} labeled {no_extend_label}")
                        break

                if not conflict:
                    await jira.add_label(ticket_key, extend_label)
                    logger.info(f"{cloud} labeled {extend_label}")

            parent = fields.get("parent")
            if parent:
                p_ticket_key = parent.get("key").split("-")[-1]
                watchers = await jira.get_watchers(p_ticket_key)
                failed_watchers = []
                for watcher in watchers["watchers"]:
                    response = await jira.add_watcher(ticket_key, watcher["key"])
                    if not response:
                        failed_watchers.append(watcher["key"])
                if len(failed_watchers) != 0 and "WATCHERS_MAP_FAIL_NOTIFIED" not in fields.get("labels"):
                    await jira.add_label(ticket_key, "WATCHERS_MAP_FAIL_NOTIFIED")
                    template_file = "watchers_fail"
                    with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
                        template = Template(_file.read())
                    submitter = description.split("\n")[0].split()[-1]
                    parameters = {
                        "ticket": ticket_key,
                    }
                    content = template.render(**parameters)
                    subject = "Failed to add watchers from parent ticket ticket to the sub-task."
                    postman = Postman(subject, submitter, "", content)
                    postman.send_email()

    return 0


if __name__ == "__main__":  # pragma: no cover
    loop = get_or_create_event_loop()
    err = loop.run_until_complete(main(loop))
    sys.exit(err)
