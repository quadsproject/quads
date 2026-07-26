#!/usr/bin/env python3
import asyncio
import logging

import aiohttp
import urllib3
from aiohttp import BasicAuth

urllib3.disable_warnings()

logger = logging.getLogger(__name__)


class Foreman(object):
    def __init__(self, url, username, password, semaphore=None):
        logger.debug(":Initializing Foreman object:")
        self.url = url
        self.username = username
        self.password = password
        if not semaphore:
            self.semaphore = asyncio.Semaphore(20)
        else:
            self.semaphore = semaphore

    async def get(self, endpoint):
        logger.debug("GET: %s" % endpoint)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url + endpoint,
                    auth=BasicAuth(self.username, self.password),
                    ssl=False,
                    timeout=60,
                ) as response:
                    result = await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return {}
        return result

    async def delete(self, endpoint):
        logger.debug("DELETE: %s" % endpoint)
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.delete(
                        self.url + endpoint,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        return response.status in (200, 204)
        except Exception as ex:
            logger.debug(ex)
            return False

    async def post(self, endpoint, data):
        logger.debug("POST: %s %s" % (endpoint, data))
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.url + endpoint,
                        json=data,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        result = await response.json(content_type=None)
        except Exception as ex:
            logger.debug(ex)
            return {}, 0
        return result, response.status

    async def get_obj_dict(self, endpoint, identifier="name"):
        response_json = await self.get(endpoint)
        objects = {}
        if "results" in response_json:
            objects = {_object[identifier]: _object for _object in response_json["results"]}
        return objects

    async def set_host_parameter(self, host_name, name, value):
        host_parameter = await self.get_host_parameter_id(host_name, name)
        _host_id = await self.get_host_id(host_name)
        if host_parameter:
            return await self.put_host_parameter(_host_id, host_parameter, value)
        else:
            return await self.post_host_parameter(_host_id, name, value)

    async def put_host_parameter(self, host_id, parameter_id, value):
        logger.debug("PUT param: {%s:%s}" % (parameter_id, value))
        endpoint = "/hosts/%s/parameters/%s" % (host_id, parameter_id)
        data = {"parameter": {"value": value}}
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        self.url + endpoint,
                        json=data,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 204]:
            logger.info("Host parameter updated successfully.")
            return True
        return False

    async def post_host_parameter(self, host_id, name, value):
        logger.debug("PUT param: {%s:%s}" % (name, value))
        endpoint = "/hosts/%s/parameters" % host_id
        data = {"parameter": {"name": name, "value": value}}
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.url + endpoint,
                        json=data,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 201, 204]:
            logger.info("Host parameter updated successfully.")
            return True
        return False

    async def update_user_password(self, login, password):
        logger.debug("PUT login pass: {%s}" % login)
        _host_id = await self.get_user_id(login)
        endpoint = "/users/%s" % _host_id
        data = {"user": {"login": login, "password": password}}
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        self.url + endpoint,
                        json=data,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 204]:
            logger.info("User password updated successfully.")
            return True
        return False

    async def put_element(self, element_name, element_id, param_name, param_value):
        params = {param_name: param_value}
        results = await self.put_elements(element_name, element_id, params)
        return results

    async def put_elements(self, element_name, element_id, params):
        logger.debug("PUT param: %s" % params)
        endpoint = "/%s/%s" % (element_name, element_id)
        data = {element_name[:-1]: params}
        try:
            async with self.semaphore:
                async with aiohttp.ClientSession() as session:
                    async with session.put(
                        self.url + endpoint,
                        json=data,
                        auth=BasicAuth(self.username, self.password),
                        ssl=False,
                        timeout=60,
                    ) as response:
                        await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status in [200, 204]:
            logger.debug("Foreman element updated successfully.")
            return True
        return False

    async def put_parameter(self, host_name, name, value):
        logger.debug("PUT param: {%s:%s}" % (name, value))
        _host_id = await self.get_host_id(host_name)
        result = await self.put_element("hosts", _host_id, name, value)
        return result

    async def put_parameters(self, host_name, params):
        logger.debug("PUT param: %s" % params)
        _host_id = await self.get_host_id(host_name)
        result = await self.put_elements("hosts", _host_id, params)
        return result

    async def put_parameters_by_name(self, host, params):
        logger.debug("PUT param: %s" % params)
        data = {}
        for param in params:
            param_name = param.get("name")
            param_value = param.get("value")
            param_identifier = param.get("identifier", "name")

            param_id = None
            if param_name == "media":
                put_name = "medium"
            else:
                put_name = param_name[:-1]
            endpoint = "/%s" % param_name
            result = await self.get(endpoint)
            if result.get("results", False):
                for item in result["results"]:
                    if item.get(param_identifier, None) == param_value:
                        param_id = item["id"]
                        break
            else:
                return False
            if param_id:
                data["%s_id" % put_name] = param_id
                data["%s_name" % put_name] = param_value
        success = await self.put_parameters(host, data)
        return success

    async def put_parameter_by_name(self, host, name, value, identifier="name"):
        logger.debug("PUT param: {%s:%s}" % (name, value))
        param_id = None
        if name == "media":
            put_name = "medium"
        else:
            put_name = name[:-1]
        endpoint = "/%s" % name
        result = await self.get(endpoint)
        for item in result["results"]:
            if identifier in item and item[identifier] == value:
                param_id = item["id"]
                break
        if param_id:
            success = await self.put_parameter(host, "%s_id" % put_name, param_id)
            success = await self.put_parameter(host, "%s_name" % put_name, value) and success
            return success
        return False

    async def verify_credentials(self):
        endpoint = "/status"
        logger.debug("GET: %s" % endpoint)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url + endpoint,
                    auth=BasicAuth(self.username, self.password),
                    ssl=False,
                    timeout=60,
                ) as response:
                    await response.json(content_type="application/json")
        except Exception as ex:
            logger.debug(ex)
            logger.error("There was something wrong with your request.")
            return False
        if response.status == 200:
            return True
        return False

    async def get_idrac_host(self, host_name):
        logger.debug("GET idrac: %s" % host_name)
        _host_id = await self.get_host_id(host_name)
        endpoint = "/hosts/%s/interfaces/" % _host_id
        result = await self.get_obj_dict(endpoint)
        for interface, _ in result.items():
            if "mgmt" in interface:
                return interface
        return None

    async def get_idrac_host_with_details(self, host_name):
        logger.debug("GET idrac: %s" % host_name)
        _host_id = await self.get_host_id(host_name)
        endpoint = "/hosts/%s/interfaces/" % _host_id
        result = await self.get_obj_dict(endpoint)
        for interface, details in result.items():
            if "mgmt" in interface:
                return details
        return None

    async def get_all_hosts(self):
        endpoint = "/hosts?per_page=9999"
        return await self.get_obj_dict(endpoint)

    async def get_host(self, hostname):
        endpoint = f"/hosts?search=name={hostname}"
        return await self.get_obj_dict(endpoint)

    async def get_broken_hosts(self):
        endpoint = "/hosts?search=params.broken_state=true"
        return await self.get_obj_dict(endpoint)

    async def get_build_hosts(self, build=True):
        endpoint = "/hosts?search=build=%s" % str(build).lower()
        return await self.get_obj_dict(endpoint)

    async def get_parametrized(self, param, value):
        endpoint = "/hosts?search=%s=%s" % (param, value)
        return await self.get_obj_dict(endpoint)

    async def get_host_id(self, host_name):
        endpoint = "/hosts?search=name=%s" % host_name
        result = await self.get_obj_dict(endpoint)
        _id = None
        if host_name in result:
            _id = result[host_name]["id"]
        return _id

    async def get_host_parameter_id(self, host_name, parameter_name):
        host_id = await self.get_host_id(host_name)
        endpoint = "/hosts/%s/parameters?search=name=%s" % (host_id, parameter_name)
        result = await self.get_obj_dict(endpoint)
        _id = None
        if parameter_name in result:
            _id = result[parameter_name]["id"]
        return _id

    async def get_user_id(self, user_name):
        endpoint = "/users?search=login=%s" % user_name
        result = await self.get_obj_dict(endpoint, "login")
        _id = None
        if user_name in result:
            _id = result[user_name]["id"]
        return _id

    async def get_role_id(self, role):
        endpoint = "/roles?search=name=%s" % role
        result = await self.get_obj_dict(endpoint)
        _id = None
        if role in result:
            _id = result[role]["id"]
        return _id

    async def get_host_param(self, host_name, param):
        _id = await self.get_host_id(host_name)
        endpoint = "/hosts/%s/parameters?search=name=%s" % (_id, param)
        result = await self.get_obj_dict(endpoint)
        if result:
            return {"result": result[param]["value"]}
        return

    async def get_host_build_status(self, host_name):
        endpoint = "/hosts?search=name=%s" % host_name
        result = await self.get_obj_dict(endpoint)
        build_status = result[host_name]["build_status"]
        return bool(build_status)

    async def get_host_extraneous_interfaces(self, host_id):
        endpoint = "/hosts/%s/interfaces" % host_id
        response_json = await self.get(endpoint)
        extraneous_interfaces = [i for i in response_json["results"] if i["identifier"] != "mgmt" and not i["primary"]]
        return extraneous_interfaces

    async def remove_extraneous_interfaces(self, host):
        _host_id = await self.get_host_id(host)
        success = True
        extraneous_interfaces = await self.get_host_extraneous_interfaces(_host_id)
        for interface in extraneous_interfaces:
            endpoint = self.url + "/hosts/%s/interfaces/%s" % (
                _host_id,
                interface["id"],
            )
            try:
                async with self.semaphore:
                    async with aiohttp.ClientSession() as session:
                        async with session.delete(
                            endpoint,
                            auth=BasicAuth(self.username, self.password),
                            ssl=False,
                            timeout=60,
                        ) as response:
                            await response.json(content_type="application/json")
            except Exception as ex:
                logger.debug(ex)
                logger.error("There was something wrong with your request.")
                success = False
                continue
            if response.status != 200:
                logger.info("Interface removed successfully.")
                success = False
        return success

    async def add_role(self, user_name, role):
        user_id = await self.get_user_id(user_name)
        role_id = await self.get_role_id(role)
        user_roles = await self.get_user_roles_ids(user_id)
        user_roles.append(role_id)
        return await self.put_element("users", user_id, "role_ids", user_roles)

    async def remove_role(self, user_name, role):
        user_id = await self.get_user_id(user_name)
        role_id = await self.get_role_id(role)
        user_roles = await self.get_user_roles_ids(user_id)
        if role_id in user_roles:
            user_roles.pop(user_roles.index(role_id))
        else:
            logger.warning("Nothing done. User does not have this role assigned.")
            return True
        return await self.put_element("users", user_id, "role_ids", user_roles)

    async def get_user_roles(self, user_id):
        endpoint = "/users/%s/roles" % user_id
        result = await self.get_obj_dict(endpoint)
        if result.get("Default role", False):
            result.pop("Default role")
        return result

    async def get_user_roles_ids(self, user_id):
        result = await self.get_user_roles(user_id)
        return [role["id"] for _, role in result.items()]

    async def get_available_os(self):
        endpoint = "/operatingsystems"
        result = await self.get(endpoint)
        return result.get("results", {})

    async def get_mediums(self, os_id):
        endpoint = f"/operatingsystems/{os_id}/media"
        result = await self.get(endpoint)
        return result.get("results", {})

    async def get_ptables(self, os_id):
        endpoint = f"/operatingsystems/{os_id}/ptables"
        result = await self.get(endpoint)
        return result.get("results", {})

    async def mark_for_build(self, host_name):
        put_result = await self.put_parameter(host_name, "build", 1)
        return put_result

    async def get_permission_ids(self, permission_names):
        ids = []
        for name in permission_names:
            result = await self.get("/permissions?search=name=%s" % name)
            for perm in result.get("results", []):
                if perm["name"] == name:
                    ids.append(perm["id"])
                    break
        return ids

    async def get_or_create_role(self, name):
        role_id = await self.get_role_id(name)
        if role_id:
            return role_id
        result, status = await self.post("/roles", {"role": {"name": name, "description": ""}})
        if status in (200, 201):
            logger.info("Created Foreman role '%s'" % name)
            return result.get("id")
        # Role may have been created by another worker between our get and post
        role_id = await self.get_role_id(name)
        if role_id:
            return role_id
        logger.error("Failed to create Foreman role '%s': HTTP %s %s" % (name, status, result))
        return None

    async def get_filters_for_role(self, role_id):
        result = await self.get("/filters?search=role_id=%s&per_page=100" % role_id)
        return result.get("results", [])

    async def role_has_permission(self, role_id, permission_name):
        for f in await self.get_filters_for_role(role_id):
            for perm in f.get("permissions", []):
                if perm.get("name") == permission_name:
                    return True
        return False

    async def cleanup_duplicate_filters(self, role_id):
        """Remove duplicate filters (same permission set) for a role, keeping the lowest ID."""
        filters = await self.get_filters_for_role(role_id)
        seen = {}
        to_delete = []
        for f in sorted(filters, key=lambda x: x["id"]):
            perm_key = frozenset(p["name"] for p in f.get("permissions", []))
            if perm_key in seen:
                to_delete.append(f["id"])
            else:
                seen[perm_key] = f["id"]
        for filter_id in to_delete:
            await self.delete("/filters/%s" % filter_id)
        if to_delete:
            logger.info("Removed %d duplicate filter(s) for role %s" % (len(to_delete), role_id))
        return len(to_delete)

    async def ensure_filter(self, role_id, permission_names, search=None):
        if await self.role_has_permission(role_id, permission_names[0]):
            return True
        permission_ids = await self.get_permission_ids(permission_names)
        filter_data = {"filter": {"role_id": role_id, "permission_ids": permission_ids}}
        if search:
            filter_data["filter"]["search"] = search
        _, status = await self.post("/filters", filter_data)
        if status in (200, 201):
            logger.info("Created filter %s for role %s" % (permission_names, role_id))
            return True
        logger.error("Failed to create filter %s for role %s: HTTP %s" % (permission_names, role_id, status))
        return False

    async def get_usergroup_id(self, name):
        result = await self.get_obj_dict("/usergroups?search=name=%s" % name)
        if name in result:
            return result[name]["id"]
        return None

    async def get_or_create_usergroup(self, name, role_ids):
        group_id = await self.get_usergroup_id(name)
        if group_id:
            return group_id
        result, status = await self.post("/usergroups", {"usergroup": {"name": name, "role_ids": role_ids}})
        if status in (200, 201):
            logger.info("Created Foreman usergroup '%s'" % name)
            return result.get("id")
        logger.error("Failed to create Foreman usergroup '%s': HTTP %s" % (name, status))
        return None

    async def add_user_to_usergroup(self, group_id, user_id):
        result = await self.get("/usergroups/%s" % group_id)
        current_ids = [u["id"] for u in result.get("users", [])]
        if user_id in current_ids:
            return True
        # POST to the nested users endpoint is atomic; no read-modify-write race.
        _, status = await self.post(
            "/usergroups/%s/users" % group_id,
            {"user": {"id": user_id}},
        )
        if status in (200, 201):
            return True
        # Fallback: the nested endpoint may not exist in older Foreman — try PUT.
        current_ids.append(user_id)
        return await self.put_element("usergroups", group_id, "user_ids", current_ids)

    async def cleanup_duplicate_memberships(self, group_id):
        result = await self.get("/usergroups/%s" % group_id)
        users = result.get("users", [])
        seen = set()
        to_remove = []
        for u in users:
            uid = u["id"]
            if uid in seen:
                to_remove.append(uid)
            else:
                seen.add(uid)
        for uid in to_remove:
            await self.delete("/usergroups/%s/users/%s" % (group_id, uid))
        if to_remove:
            logger.info("Removed %d duplicate user membership(s) from usergroup %s" % (len(to_remove), group_id))
        return len(to_remove)

    async def get_or_create_cloud_user(self, login, password, mail, auth_source_id=1):
        user_id = await self.get_user_id(login)
        if user_id:
            return user_id
        result, status = await self.post(
            "/users",
            {
                "user": {
                    "login": login,
                    "password": password,
                    "mail": mail,
                    "auth_source_id": auth_source_id,
                    "admin": False,
                }
            },
        )
        if status in (200, 201):
            logger.info("Created Foreman user '%s'" % login)
            return result.get("id")
        # User may have been created by another process between our get and post
        user_id = await self.get_user_id(login)
        if user_id:
            return user_id
        logger.error("Failed to create Foreman user '%s': HTTP %s %s" % (login, status, result))
        return None

    async def prepare_host_provisioning(self, host_name: str, cloud: str, os_type: str) -> bool:

        results = []

        try:
            available_os = await self.get_available_os()
            os_id = next((os["id"] for os in available_os if os["title"] == os_type), None)

            if not os_id:
                logger.error(f"OS type {os_type} not found in Foreman")
                return False

            params = [{"name": "operatingsystems", "value": os_type, "identifier": "title"}]

            available_mediums = await self.get_mediums(os_id)
            params.append({"name": "media", "value": available_mediums[0]["name"]})

            available_ptables = await self.get_ptables(os_id)
            params.append({"name": "ptables", "value": available_ptables[0]["name"]})

            mark_for_build_result = await self.mark_for_build(host_name)
            results.append(mark_for_build_result)

            put_param_result = await self.put_parameters_by_name(host_name, params)
            results.append(put_param_result)

            owner_id = await self.get_user_id(cloud)
            host_id = await self.get_host_id(host_name)
            put_result = await self.put_element("hosts", host_id, "owner_id", owner_id)
            results.append(put_result)

            for result in results:
                if isinstance(result, Exception) or not result:
                    logger.error("There was something wrong setting Foreman host parameters.")
                    return False

            return True
        except Exception as ex:
            self.logger.error(f"Error setting up Foreman for {host_name}: {ex}")
            return False
