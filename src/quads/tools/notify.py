#!/usr/bin/env python3
import asyncio
import logging
import os

from datetime import datetime, timedelta
from enum import Enum

from jinja2 import Template
from rich.logging import RichHandler
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Column
from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.plugins.dispatchers.email import get_email_dispatcher
from quads.plugins.dispatchers.chat import get_chat_dispatcher
from quads.plugins.dispatchers.dayzero import get_dayzero_dispatcher

logging.basicConfig(level=logging.INFO, format="%(message)s", datefmt="[%X]", handlers=[RichHandler()])
logger = logging.getLogger(__name__)
quads = QuadsApi(Config)


class Days(Enum):
    ONE_DAY = 1
    THREE_DAYS = 3
    FIVE_DAYS = 5
    SEVEN_DAYS = 7

    @classmethod
    def less_than(cls, max_days):
        return [day for day in cls if day.value <= max_days]


async def create_initial_message(real_owner, cloud, cloud_info, ticket, cc, is_self_schedule=False):
    template_file = "initial_message"
    infra_location = Config["infra_location"]
    cc_users = [_cc_user.strip() for _cc_user in Config.plugins["email"]["report_cc"].split(",")]
    for user in cc:
        cc_users.append("%s@%s" % (user, Config["domain"]))

    if Config.plugins["email"]["enabled"]:
        with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
            template = Template(_file.read())
        content = template.render(
            cloud_info=cloud_info,
            cloud=cloud,
            quads_url=Config["quads_url"],
            real_owner=real_owner,
            password=f"{infra_location}@{ticket}",
            foreman_url=Config.plugins["foreman"]["url"],
            is_self_schedule=is_self_schedule,
        )

        email_dispatcher = get_email_dispatcher()
        recipient = "%s@%s" % (real_owner, Config["domain"])
        await email_dispatcher.send_mail(
            subject="New QUADS Assignment Allocated - %s %s" % (cloud, ticket),
            content=content,
            recipients=[recipient],
            cc=cc_users,
        )

    message = "QUADS: %s is now active, choo choo! - %s/assignments/#%s -  %s %s" % (
        cloud_info,
        Config["quads_url"],
        cloud,
        real_owner,
        Config.plugins["email"]["report_cc"],
    )

    chat_dispatcher = get_chat_dispatcher()
    await chat_dispatcher.send_message(
        message=message,
    )


def create_message(
    cloud,
    assignment_obj,
    day,
    cloud_info,
    host_list_expire,
):
    template_file = "message"
    real_owner = assignment_obj.owner
    ticket = assignment_obj.ticket
    cc = assignment_obj.ccuser

    cc_users = [_cc_user.strip() for _cc_user in Config.plugins["email"]["report_cc"].split(",")]
    for user in cc:
        cc_users.append("%s@%s" % (user, Config["domain"]))
    with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
        template = Template(_file.read())
    quads_request_url = Config.quads_request_url
    content = template.render(
        days_to_report=day,
        cloud_info=cloud_info,
        quads_url=Config["quads_url"],
        quads_request_url=quads_request_url,
        quads_request_deadline_day=Config["quads_request_deadline_day"],
        quads_notify_until_extended=Config["quads_notify_until_extended"],
        cloud=cloud,
        hosts=host_list_expire,
    )

    email_dispatcher = get_email_dispatcher()
    recipient = "%s@%s" % (real_owner, Config["domain"])
    email_dispatcher.send_mail_sync(
        subject="QUADS upcoming expiration for %s - %s" % (cloud, ticket),
        content=content,
        recipients=[recipient],
        cc=cc_users,
    )


def create_future_initial_message(cloud, assignment_obj, cloud_info):
    template_file = "future_initial_message"
    ticket = assignment_obj.ticket
    cc_users = [_cc_user.strip() for _cc_user in Config.plugins["email"]["report_cc"].split(",")]
    for user in assignment_obj.ccuser:
        cc_users.append("%s@%s" % (user, Config["domain"]))
    with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
        template = Template(_file.read())
    content = template.render(
        cloud_info=cloud_info,
        quads_url=Config["quads_url"],
        is_self_schedule=assignment_obj.is_self_schedule,
    )

    email_dispatcher = get_email_dispatcher()
    recipient = "%s@%s" % (assignment_obj.owner, Config["domain"])
    email_dispatcher.send_mail_sync(
        subject="New QUADS Assignment Defined for the Future: %s - %s" % (cloud, ticket),
        content=content,
        recipients=[recipient],
        cc=cc_users,
    )


def create_future_message(
    cloud,
    assignment_obj,
    future_days,
    cloud_info,
    host_list_expire,
):
    ticket = assignment_obj.ticket
    cc_users = [_cc_user.strip() for _cc_user in Config.plugins["email"]["report_cc"].split(",")]
    for user in assignment_obj.ccuser:
        cc_users.append("%s@%s" % (user, Config["domain"]))
    template_file = "future_message"
    with open(os.path.join(Config.TEMPLATES_PATH, template_file)) as _file:
        template = Template(_file.read())
    content = template.render(
        days_to_report=future_days,
        cloud_info=cloud_info,
        quads_url=Config["quads_url"],
        cloud=cloud,
        hosts=host_list_expire,
    )

    email_dispatcher = get_email_dispatcher()
    recipient = "%s@%s" % (assignment_obj.owner, Config["domain"])
    email_dispatcher.send_mail_sync(
        subject="QUADS upcoming assignment notification - %s - %s" % (cloud, ticket),
        content=content,
        recipients=[recipient],
        cc=cc_users,
    )


def main(_logger=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    global logger
    if _logger:
        logger = _logger

    _all_clouds = quads.get_clouds()
    _assignments = quads.filter_assignments({"active": True, "validated": True})

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}", table_column=Column(min_width=30)),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task("Sending notifications", total=len(_assignments))
        for ass in _assignments:
            progress.update(task, description=f"[cyan]{ass.cloud.name}[/]")

            payload = {"cloud": ass.cloud.name}
            current_schedules = []
            try:
                current_schedules = quads.get_current_schedules(payload)
            except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                logger.debug(str(ex))
                logger.error("Could not get current schedules")
                progress.advance(task)
                continue

            cloud_info = "%s: %s (%s)" % (
                ass.cloud.name,
                len(current_schedules),
                ass.description,
            )
            if not ass.notification.initial:
                logger.info("=============== Initial Message")
                loop.run_until_complete(
                    create_initial_message(
                        ass.owner,
                        ass.cloud.name,
                        cloud_info,
                        ass.ticket,
                        ass.ccuser,
                        ass.is_self_schedule,
                    )
                )
                try:
                    quads.update_notification(ass.notification.id, {"initial": True})
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    logger.debug(str(ex))
                    logger.error("Could not update notification: %s." % ass.notification.id)

                dayzero_dispatcher = get_dayzero_dispatcher()
                loop.run_until_complete(dayzero_dispatcher.execute(ass.cloud.name))

            if Config.plugins["email"]["enabled"] and not ass.is_self_schedule:
                for day in Days:
                    future_schedules = []
                    future = datetime.now() + timedelta(days=day.value)
                    future_date = "%4d-%.2d-%.2dT22:00" % (
                        future.year,
                        future.month,
                        future.day,
                    )
                    payload = {"cloud": ass.cloud.name, "date": future_date}
                    try:
                        future_schedules = quads.get_current_schedules(payload)
                    except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                        logger.debug(str(ex))
                        logger.error("Could not get current schedules")
                        continue

                    current_hosts = [sched.host.name for sched in current_schedules]
                    future_hosts = [sched.host.name for sched in future_schedules]
                    host_list = set(current_hosts) - set(future_hosts)
                    if host_list and future > current_schedules[0].end:
                        if not getattr(ass.notification, day.name.lower()):
                            logger.info("=============== Expiration Notification")
                            cloud = ass.cloud.name
                            create_message(
                                cloud,
                                ass,
                                day.value,
                                cloud_info,
                                host_list,
                            )

                            try:
                                quads.update_notification(ass.notification.id, {day.name.lower(): True})
                            except (APIServerException, APIBadRequest) as ex:
                                logger.debug(str(ex))
                                logger.error("Could not update notification: %s." % ass.notification.id)

                            break

            progress.advance(task)

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}", table_column=Column(min_width=30)),
        BarColumn(),
        MofNCompleteColumn(),
    ) as progress:
        task = progress.add_task("Processing clouds", total=len(_all_clouds))
        for cloud in _all_clouds:
            progress.update(task, description=f"[cyan]{cloud.name}[/]")
            ass = quads.get_active_cloud_assignment(cloud.name)
            if not ass:
                progress.advance(task)
                continue
            if cloud.name != Config["spare_pool_name"] and ass.owner not in ["quads", None]:
                payload = {"cloud": ass.cloud.name}
                current_schedules = []
                try:
                    current_schedules = quads.get_current_schedules(payload)
                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                    logger.debug(str(ex))
                    logger.error("Could not get current schedules")
                    progress.advance(task)
                    continue

                cloud_info = "%s: %s (%s)" % (
                    cloud.name,
                    len(current_schedules),
                    ass.description,
                )

                if not ass.notification.pre_initial and Config.plugins["email"]["enabled"]:
                    logger.info("=============== Future Initial Message")
                    create_future_initial_message(
                        cloud.name,
                        ass,
                        cloud_info,
                    )

                    try:
                        quads.update_notification(ass.notification.id, {"pre_initial": True})
                    except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                        logger.debug(str(ex))
                        logger.error("Could not update notification: %s." % ass.notification.id)

                for day in Days:
                    future_schedules = []
                    if not ass.notification.pre and ass.validated:
                        future = datetime.now() + timedelta(days=day.value)
                        future_date = "%4d-%.2d-%.2dT22:00" % (
                            future.year,
                            future.month,
                            future.day,
                        )
                        payload = {"cloud": ass.cloud.name, "date": future_date}
                        try:
                            future_schedules = quads.get_current_schedules(payload)
                        except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                            logger.debug(str(ex))
                            logger.error("Could not get current schedules")
                            continue

                        if len(future_schedules) > 0:
                            current_hosts = [sched.host.name for sched in current_schedules]
                            future_hosts = [sched.host.name for sched in future_schedules]
                            host_list = set(current_hosts) - set(future_hosts)
                            if host_list:
                                logger.info("=============== Additional Message")
                                create_future_message(
                                    cloud.name,
                                    ass,
                                    day.value,
                                    cloud_info,
                                    host_list,
                                )

                                try:
                                    quads.update_notification(ass.notification.id, {"pre": True})
                                except (APIServerException, APIBadRequest) as ex:  # pragma: no cover
                                    logger.debug(str(ex))
                                    logger.error("Could not update notification: %s." % ass.notification.id)

                                break

            progress.advance(task)


if __name__ == "__main__":  # pragma: no cover
    main()
