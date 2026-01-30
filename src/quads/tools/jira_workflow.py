#!/usr/bin/env python3
import asyncio
import logging
import sys

from quads.quads_api import QuadsApi
from quads.tools.external.jira import Jira, JiraException
from quads.config import Config
from quads.tools.helpers import get_or_create_event_loop

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
quads = QuadsApi(Config)


async def main(_loop):
    try:
        jira = Jira(
            Config["jira_url"],
            loop=_loop,
        )
    except JiraException as ex:
        logger.error(ex)
        return 1

    all_pending_tickets = await jira.get_all_pending_tickets()
    all_pending_tickets = all_pending_tickets["issues"]
    jira_ticket_keys = []
    for ticket in all_pending_tickets:
        ticket_key = ticket.get("key").split("-")[-1]
        fields = ticket.get("fields")
        parent = fields.get("parent")
        if parent is None:
            jira_ticket_keys.append(ticket_key)

    assignments = quads.get_active_assignments()
    cloud_ticket_keys = [assignment.ticket for assignment in assignments]
    expired_keys = [key for key in jira_ticket_keys if key not in cloud_ticket_keys]

    for ticket_key in expired_keys:
        transitions = await jira.get_transitions(ticket_key)
        transition_result = False
        for transition in transitions:
            t_name = transition.get("name")
            if t_name and t_name.lower() == "done":
                transition_id = transition.get("id")
                transition_result = await jira.post_transition(ticket_key, transition_id)
                break

        if not transition_result:
            logger.warning(f"Failed to update ticket status, ticket key {ticket_key}, SKIPPING.")

    return 0


if __name__ == "__main__":  # pragma: no cover
    loop = get_or_create_event_loop()
    err = loop.run_until_complete(main(loop))
    sys.exit(err)
