#!/usr/bin/env python3
"""
QUADS API client for web services.
Provides a standardized way for web components to communicate with the QUADS server API.
"""
import os
from datetime import datetime
from typing import List, Dict, Any

import aiohttp
import requests
from aiohttp import BasicAuth
from requests.auth import HTTPBasicAuth

from quads.config import Config
from quads.server.models import Host


class QuadsApiClient:
    """Synchronous API client for QUADS server communication."""

    def __init__(self, config: Config = None):
        self.config = config or Config
        self.base_url = self.config.API_URL
        self.username = self.config.get("quads_api_username")
        self.password = self.config.get("quads_api_password")
        self.verify_ssl = self.config.get("verify_ssl", False)

    def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a synchronous GET request to the API."""
        try:
            url = os.path.join(self.base_url, endpoint)
            response = requests.get(
                url,
                params=params,
                auth=HTTPBasicAuth(self.username, self.password),
                verify=self.verify_ssl,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Log the error but return empty result to maintain compatibility
            print(f"API request failed: {e}")
            return {}

    def get_hosts(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get hosts from the API with optional filters."""
        params = filters or {}
        response = self._get("hosts", params)
        if isinstance(response, list):
            return response
        return []

    def get_active_hosts(self) -> List[Dict[str, Any]]:
        """Get active hosts (not retired or broken)."""
        return self.get_hosts({"retired": False, "broken": False})

    def get_monthly_schedules(self, start: datetime, end: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """Get schedule data for a date range, grouped by hostname."""
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
        }
        response = self._get("schedules/hosts_range", params)
        if isinstance(response, dict):
            return response
        return {}

    def get_current_schedules(
        self, date: datetime = None, hostname: str = None, cloud: str = None
    ) -> List[Dict[str, Any]]:
        """Get current schedules with optional filters."""
        params = {}
        if date:
            params["date"] = date.strftime("%Y-%m-%dT%H:%M")
        if hostname:
            params["host"] = hostname
        if cloud:
            params["cloud"] = cloud

        response = self._get("schedules/current", params)
        if isinstance(response, list):
            return response
        return []

    def get_hosts_batch(self, offset: int = 0, limit: int = 100, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get hosts in batches for progressive loading."""
        params = filters or {}
        params.update({"offset": offset, "limit": limit, "retired": False, "broken": False})

        response = self._get("hosts/batch", params)
        if isinstance(response, dict):
            return response
        return {"hosts": [], "total": 0, "has_more": False}

    def get_schedules_for_hosts(
        self, hostnames: List[str], start: datetime, end: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get schedules for specific hosts within a date range."""
        params = {
            "hostnames": ",".join(hostnames),
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
        }
        response = self._get("schedules/hosts_batch", params)
        if isinstance(response, dict):
            return response
        return {}


class QuadsApiAsync:
    """Asynchronous API client for QUADS server communication (for compatibility)."""

    def __init__(self, config: Config = None):
        self.config = config or Config
        self.base_url = self.config.API_URL
        self.username = self.config.get("quads_api_username")
        self.password = self.config.get("quads_api_password")
        self.verify_ssl = self.config.get("verify_ssl", False)

    async def async_get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make an asynchronous GET request to the API."""
        try:
            async with aiohttp.ClientSession() as session:
                url = os.path.join(self.base_url, endpoint)
                async with session.get(
                    url,
                    params=params,
                    auth=BasicAuth(self.username, self.password),
                    timeout=60,
                    verify_ssl=self.verify_ssl,
                ) as response:
                    result = await response.json()
        except Exception as e:
            # Log the error but return empty result to maintain compatibility
            print(f"Async API request failed: {e}")
            result = {}
        return result

    async def get_monthly_schedules(self, start: datetime, end: datetime) -> Dict[str, List[Dict[str, Any]]]:
        """Get schedule data for a date range, grouped by hostname."""
        params = {
            "start": start.strftime("%Y-%m-%dT%H:%M"),
            "end": end.strftime("%Y-%m-%dT%H:%M"),
        }
        schedules = await self.async_get("schedules/hosts_range", params)
        return schedules

    async def get_current_schedules(self) -> List[Dict[str, Any]]:
        """Get current schedules."""
        schedules = await self.async_get("schedules/current")
        return schedules if isinstance(schedules, list) else []

    async def async_filter_hosts(self, data: Dict[str, Any]) -> List[Host]:
        """Get hosts with filters and convert to Host objects."""
        response = await self.async_get("hosts", data)
        hosts = []
        if isinstance(response, list):
            for host_data in response:
                try:
                    host_obj = Host().from_dict(data=host_data)
                    hosts.append(host_obj)
                except Exception:
                    # If conversion fails, skip this host
                    continue
        return hosts
