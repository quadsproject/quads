#!/usr/bin/env python3
import aiohttp
import asyncio
import logging
import urllib3
from aiohttp import BasicAuth

from quads.config import Config

urllib3.disable_warnings()

logger = logging.getLogger(__name__)


class JiraException(Exception):
    pass


class Jira(object):
    def __init__(self, url, username=None, password=None, semaphore=None, loop=None):
        logger.debug(":Initializing Jira object:")
        self.url = url
        self.username = username
        self.password = password
        self.ticket_queue = Config["ticket_queue"]
        if not loop:
            self.loop = asyncio.new_event_loop()
            self.new_loop = True
        else:
            self.loop = loop
            self.new_loop = False
        if not semaphore:
            self.semaphore = asyncio.Semaphore(20)
        else:
            self.semaphore = semaphore

        jira_auth = Config.jira_auth
        self.auth = None
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if jira_auth and jira_auth == "token":
            token = Config.jira_token
            if not token:
                raise JiraException(
                    "Jira authentication is set to BearerAuth but no "
                    "token has been defined on the configuration file"
                )
            payload = "Bearer: %s" % token
            self.headers["Authorization"] = payload
        else:
            if self.username and self.password:
                self.auth = BasicAuth(self.username, self.password)
            else:
                raise JiraException(
                    "Jira authentication is set to BasicAuth but no username or password have been defined"
                )

    def __exit__(self):
        if self.new_loop:
            self.loop.close()

    async def get_request(self, endpoint):
        logger.debug("GET: %s" % endpoint)
        try:
            async with aiohttp.ClientSession(
                headers=self.headers,
                auth=self.auth,
                loop=self.loop,
            ) as session:
                async with session.get(
                    self.url + endpoint,
                    verify_ssl=False,
                ) as response:
                    result = await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return None
        if response.status == 404:
            logger.error("Resource not found: %s" % self.url + endpoint)
            return None
        return result

    async def post_request(self, endpoint, payload):
        logger.debug("POST: {%s:%s}" % (endpoint, payload))
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession(headers=self.headers, auth=self.auth, loop=self.loop) as session:
                    async with session.post(
                        self.url + endpoint,
                        json=payload,
                        headers=self.headers,
                        verify_ssl=False,
                    ) as response:
                        if response.status != 204:
                            _response = await response.json(content_type="application/json")
                            logger.debug("Response: %s" % _response)
                        else:
                            _response = response
                            logger.debug("Response: %s" % response)
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 201, 204]:
            logger.info("Post successful.")
            return True, _response
        if response.status == 404:
            logger.error("Resource not found: %s" % self.url + endpoint)
        return False, _response

    async def put_request(self, endpoint, payload):
        logger.debug("POST: {%s:%s}" % (endpoint, payload))
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession(headers=self.headers, auth=self.auth, loop=self.loop) as session:
                    async with session.put(
                        self.url + endpoint,
                        json=payload,
                        verify_ssl=False,
                    ) as response:
                        if response.status != 204:
                            _response = await response.json(content_type="application/json")
                            logger.debug("Response: %s" % _response)
                        else:
                            logger.debug("Response: %s" % response)
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 201, 204]:
            logger.info("Post successful.")
            return True
        if response.status == 404:
            logger.error("Resource not found: %s" % self.url + endpoint)
        return False

    async def create_ticket(self, summary, description, labels=None):
        """Create a Jira ticket."""
        if labels is None:
            labels = []
        endpoint = "/issue/"
        logger.debug("POST new ticket")
        short_summary = summary.split("\r")
        title = f"{short_summary[0]}"

        data = {
            "fields": {
                "project": {"key": self.ticket_queue},
                "issuetype": {"name": "Task"},
                "summary": title,
                "description": description,
            }
        }
        if labels:
            data["fields"].update({"labels": labels})

        result, response = await self.post_request(endpoint, data)
        return response

    async def create_subtask(self, parent_ticket, cloud, description, type_of_subtask):
        """Create a Jira subtask for a specified parent ticket."""
        endpoint = "/issue/"
        logger.debug("POST new subtask")
        title = f"{cloud} {type_of_subtask}"

        data = {
            "fields": {
                "project": f'"{self.ticket_queue}"',
                "issuetype": {"id": "10015"},
                "parent": {"key": f"{self.ticket_queue}-{parent_ticket}"},
                "summary": title,
                "labels": [type_of_subtask.upper()],
                "description": description,
            }
        }
        result, response = await self.post_request(endpoint, data)
        return response

    async def add_watcher(self, ticket, watcher):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s/watchers" % issue_id
        logger.debug("POST transition: {%s:%s}" % (issue_id, watcher))
        data = watcher
        result, response = await self.post_request(endpoint, data)
        return result

    async def add_label(self, ticket, label):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s" % issue_id
        data = {"update": {"labels": [{"add": label}]}}
        response = await self.put_request(endpoint, data)
        return response

    async def post_comment(self, ticket, comment):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s/comment" % issue_id
        payload = {"body": comment}
        result, response = await self.post_request(endpoint, payload)
        return result

    async def post_transition(self, ticket, transition):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s/transitions" % issue_id
        payload = {"transition": {"id": transition}}
        result, response = await self.post_request(endpoint, payload)
        return result

    async def get_transitions(self, ticket):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s/transitions" % issue_id
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get transitions")
            return []

        transitions = result.get("transitions")
        if transitions:
            return transitions
        else:
            logger.error("No transitions found under %s" % issue_id)
            return []

    async def get_project_transitions(self):
        endpoint = "/project/%s/statuses" % self.ticket_queue
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get project transitions")
            return []

        transitions = result[0].get("statuses")
        if transitions:
            return transitions
        else:
            logger.error("No transitions found under %s" % self.ticket_queue)
            return []

    async def get_transition_id(self, status):
        transitions = await self.get_project_transitions()
        for transition in transitions:
            if transition["name"].lower() == status.lower():
                return transition["id"]

    async def get_ticket(self, ticket):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s" % issue_id
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get ticket")
            return None
        return result

    async def get_watchers(self, ticket):
        issue_id = "%s-%s" % (self.ticket_queue, ticket)
        endpoint = "/issue/%s/watchers" % issue_id
        logger.debug("GET watchers: %s" % endpoint)
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get watchers")
            return None
        return result

    async def get_user_by_email(self, email):
        """Find a Jira user by email."""
        endpoint = f"/user/search?query={email}"
        logger.debug("GET user: %s" % endpoint)
        result = await self.get_request(endpoint)
        if not result:
            logger.error("User not found")
            return None
        for user in result:
            if user.get("emailAddress") == email:
                return user
        return None

    async def get_all_pending_tickets(self):
        transition_id = await self.get_transition_id("In Progress")
        query = {"status": transition_id}
        logger.debug("GET cloud access active tickets")
        result = await self.search_tickets(query)
        if not result:
            logger.error("Failed to get cloud access active tickets")
            return None
        return result

    async def get_pending_tickets(self):
        query = {"statusCategory": 4, "labels": "EXTENSION"}
        logger.debug("GET pending tickets")
        result = {"issues": []}
        result_extension = await self.search_tickets(query)
        if result_extension:
            result["issues"] += result_extension["issues"]
        query_expand = {"statusCategory": 4, "labels": "EXPANSION"}
        result_expand = await self.search_tickets(query_expand)
        if result_expand:
            result["issues"] += result_expand["issues"]
        if not result["issues"]:  # pragma: no cover
            logger.error("Failed to get pending tickets")
            return None
        return result

    async def search_tickets(self, query=None):
        project = {"project": f'"{self.ticket_queue}"'}
        prefix = "/search/jql?jql="
        query_items = []

        if not query:
            query = project
        else:
            query.update(project)

        for k, v in query.items():
            query_items.append(f"{k}={v}")

        jql = " AND ".join(query_items)
        endpoint = f"{prefix}{jql}"
        logger.debug("GET pending tickets: %s" % endpoint)
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get pending tickets")
            return None
        return result

    async def get_field_allowed_values(self, field_id, ticket_id=5198):
        """Get list of allowed values from JIRA API for a specified field."""
        endpoint = f"/issue/{self.ticket_queue}-{ticket_id}/editmeta"
        result = await self.get_request(endpoint)
        if not result:
            logger.error("Failed to get allowed values")
            return None
        try:
            result = result["fields"][f"customfield_{field_id}"]["allowedValues"]
            result = [entry["value"] for entry in result if not entry["value"].startswith("One or more of the")]
        except (ValueError, AttributeError):
            logger.error("Failed to get allowed values")
        return result
