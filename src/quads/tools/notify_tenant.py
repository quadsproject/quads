#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import requests

from datetime import datetime, timedelta
from enum import Enum
from jinja2 import Template

from quads.config import Config
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.tools.external.netcat import Netcat
from quads.tools.external.postman import Postman
from quads.tools.external.jira import Jira, JiraException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def post_message(args, ticket, description, cloud_name):
    quads = QuadsApi(Config)
    logger.info(
        f"Posting message.  Message file = {args.message}, "
        + f"Subject = {args.subject}, "
        + f"ticket = {ticket}, description = {description}"
    )
    try:
        with open(os.path.join(args.message)) as _file:
            template = Template(f"Subject: {args.subject}\n\n" + _file.read())
    except Exception as e:
        logger.info(f"{e}")
        return False
    content = template.render(
        description=description,
        ticket=ticket,
        cloud_name=cloud_name,
    )
    loop = asyncio.get_event_loop()
    try:
        jira = Jira(
            Config["jira_url"],
            Config["jira_username"],
            Config["jira_password"],
            loop=loop,
        )
    except JiraException as ex:  # pragma: no cover
        logger.error(ex)
        return False

    _ass = quads.filter_assignments({"active": True, "validated": True, "cloud": cloud_name})[0]
    result = loop.run_until_complete(jira.post_comment(_ass.ticket, content))
    if not result:
        logger.warning("Failed to update Jira ticket")

    return result


def send_message(args, owner, ccuser, ticket, description, cloud_name):
    logger.info(
        f"Sending message.  Message file = {args.message}, "
        + f"Subject = {args.subject}, owner = {owner}, ccuser = {ccuser}, "
        + f"ticket = {ticket}, description = {description}"
    )
    cc_users = [_cc_user.strip() for _cc_user in Config["report_cc"].split(",")]
    for user in ccuser:
        cc_users.append("%s@%s" % (user, Config["domain"]))
    try:
        with open(os.path.join(args.message)) as _file:
            template = Template(_file.read())
    except Exception as e:  # pragma: no cover
        logger.info(f"{e}")
        return False
    content = template.render(
        description=description,
        ticket=ticket,
        cloud_name=cloud_name,
    )
    postman = Postman(
        "INFO: [%s] %s" % (cloud_name, args.subject),
        owner,
        cc_users,
        content,
    )
    result = postman.send_email()
    return result


def determine_action(args):
    quads = QuadsApi(Config)
    results = []
    if args.cloud:
        cloud_names = args.cloud.split()
        for _cloud_name in cloud_names:
            _cloud = None
            try:
                _cloud = quads.get_cloud(_cloud_name)
            except (APIServerException, APIBadRequest) as ex:
                logger.debug(str(ex))
            if not _cloud:
                logger.error(f"Cloud: {_cloud_name} not found")
            else:
                logger.info(f"Cloud: {_cloud_name}")
                if _cloud_name == "cloud01":
                    logger.info(f"Skipping notification for {_cloud_name}. This is used for available hosts.")
                else:
                    hosts = quads.filter_hosts({"cloud": _cloud_name, "retired": False})
                    host_count = len(hosts)
                    if host_count > 0:
                        _ass = quads.filter_assignments({"active": True, "validated": True, "cloud": _cloud_name})[0]
                        logger.info(
                            f"Sending notification for {_cloud_name}, with {host_count} hosts.  Owner = {_ass.owner}, cc_users = {_ass.ccuser}"
                        )
                        if args.email:
                            send_message(args, _ass.owner, _ass.ccuser, _ass.ticket, _ass.description, _cloud_name)
                        if args.post:
                            result = post_message(args, _ass.ticket, _ass.description, _cloud_name)
                            results.append(result)
                    else:
                        logger.info(f"Skipping notification for {_cloud_name}, no hosts found")

    if args.all:
        _clouds = quads.get_clouds()
        for _cloud_obj in _clouds:
            logger.info(f"Cloud: {_cloud_obj.name}")
            hosts = quads.filter_hosts({"cloud": _cloud_obj.name, "retired": False})
            if _cloud_obj.name == "cloud01":
                logger.info(f"Skipping notification for {_cloud_obj.name}. This is used for available hosts.")
            else:
                host_count = len(hosts)
                if host_count > 0:
                    _ass = quads.filter_assignments({"active": True, "validated": True, "cloud": _cloud_obj.name})[0]
                    logger.info(
                        f"Sending notification for {_cloud_obj.name}. with {host_count} hosts.  Owner = {_ass.owner}, cc_users = {_ass.ccuser}"
                    )
                    if args.email:
                        send_message(args, _ass.owner, _ass.ccuser, _ass.ticket, _ass.description, _cloud_obj.name)
                    if args.post:
                        result = post_message(args, _ass.ticket, _ass.description, _cloud_obj.name)
                        results.append(result)
                else:
                    logger.info(f"Skipping notification for {_cloud_obj.name}, no hosts found")

    if args.rack:
        rack_names = args.rack.split()
        hosts = quads.filter_hosts({"retired": False})
        clouds_in_racks = []
        for _host_obj in hosts:
            if _host_obj.name.startswith(tuple(rack_names)):
                clouds_in_racks.append(_host_obj.cloud.name)
        for cloud_name in sorted(set(clouds_in_racks)):
            logger.info(f"Cloud: {cloud_name}")
            _ass = quads.filter_assignments({"active": True, "validated": True, "cloud": cloud_name})[0]
            logger.info(f"Sending notification for {cloud_name}. Owner = {_ass.owner}, cc_users = {_ass.ccuser}")
            if args.email:
                send_message(args, _ass.owner, _ass.ccuser, _ass.ticket, _ass.description, cloud_name)
            if args.post:
                result = post_message(args, _ass.ticket, _ass.description, cloud_name)
                results.append(result)

    return results


def verify_argparse(args):
    if not any([getattr(args, option) for option in ["all", "cloud", "rack"]]):
        logger.error("Please select at least one option from --all, --cloud, or --rack")
        exit(1)
    if args.rack and (args.all or args.cloud):
        logger.error("Argument --rack cannot be used with either --all or --cloud")
        exit(1)


def main():  # pragma: no cover
    parser = argparse.ArgumentParser(description="Notification tool to send messages to tenants")
    parser.add_argument(
        "--message",
        dest="message",
        type=str,
        default=None,
        help="Path to file containing message contents",
        required=True,
    )
    parser.add_argument(
        "--cloud",
        dest="cloud",
        type=str,
        default=None,
        help="List of allocations to target, e.g. 'cloud02 cloud03 cloud07'",
    )
    parser.add_argument(
        "--all",
        dest="all",
        action="store_true",
        help="Determine whether notification should be sent to all active allocations",
    )
    parser.add_argument(
        "--rack",
        dest="rack",
        type=str,
        default=None,
        help="Racks to consider when sending notification, e.g. 'd30 d31 d32'",
    )
    parser.add_argument(
        "--email",
        dest="email",
        action="store_true",
        help="Determine whether email should be sent",
    )
    parser.add_argument(
        "--post",
        dest="post",
        action="store_true",
        help="Determine whether message should be posted to ticketing system",
    )
    parser.add_argument(
        "--subject",
        dest="subject",
        type=str,
        default=None,
        help="Notification subject line",
        required=True,
    )

    args = parser.parse_args()
    verify_argparse(args)
    determine_action(args)


if __name__ == "__main__":  # pragma: no cover
    main()
