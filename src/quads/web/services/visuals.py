#!/usr/bin/env python3
import calendar
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from quads.helpers.utils import first_day_month
from .api_client import QuadsApiClient


class VisualsService:
    """Service class for generating visual allocation data for the QUADS system."""

    def __init__(self):
        self.colors = []
        self.emojis = []
        self.assignment_colors = {}
        self.api_client = QuadsApiClient()
        self.generate_colors()
        # Simple in-memory cache with TTL
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    def random_color(self) -> str:
        """Generate a random color in hex format."""

        def rand():
            return random.randint(100, 255)

        return "#%02X%02X%02X" % (rand(), rand(), rand())

    def generate_colors(self) -> None:
        """Generate color and emoji palettes for assignments."""
        # Use proper emoji Unicode ranges to avoid Chinese characters
        emoji_ranges = [
            # Emoticons (smiley faces)
            range(128512, 128591),  # 😀-😯
            # Miscellaneous Symbols and Pictographs
            range(127744, 127776),  # 🌀-🌟
            # Transport and Map Symbols
            range(128640, 128704),  # 🚀-🛀
            # Geometric Shapes Extended
            range(128992, 129004),  # 🟠-🟫 (colored circles/squares)
            # Additional symbols
            range(9728, 9732),  # ☀-☃ (weather symbols)
            range(9742, 9750),  # ☎-☖ (misc symbols)
        ]

        all_samples = []
        for emoji_range in emoji_ranges:
            all_samples.extend(emoji_range)

        # Select a reasonable number of emojis, avoiding problematic ones
        samples = random.sample(all_samples, min(100, len(all_samples)))
        self.emojis = samples
        self.colors = [self.random_color() for _ in range(100)]
        self.colors[0] = "#A9A9A9"  # Default color for unallocated

    def _get_cache_key(self, method: str, *args, **kwargs) -> str:
        """Generate a cache key for method with arguments."""
        key_data = f"{method}:{args}:{sorted(kwargs.items())}".encode("utf-8")
        return hashlib.md5(key_data).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get data from cache if not expired."""
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self._cache_ttl):
                return data
            else:
                # Remove expired entry
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set data in cache with current timestamp."""
        self._cache[cache_key] = (data, datetime.now())

        # Simple cache cleanup - remove entries older than 2x TTL
        cleanup_threshold = datetime.now() - timedelta(seconds=self._cache_ttl * 2)
        expired_keys = [key for key, (_, timestamp) in self._cache.items() if timestamp < cleanup_threshold]
        for key in expired_keys:
            del self._cache[key]

    def process_host_days(self, schedules: List[Dict], days: int, month: int, year: int) -> Tuple[List[Dict], int]:
        """
        Process days for a single host and return day data with allocation count.

        Args:
            schedules: List of schedule dictionaries for this host
            days: Number of days in the month
            month: Month number
            year: Year number

        Returns:
            Tuple of (day_data_list, allocated_count)
        """
        allocated_count = 0
        day_data = []

        for day in range(1, days + 1):
            cell_date = f"{year}-{month:02d}-{day:02d} 01:00"
            cell_time = datetime.strptime(cell_date, "%Y-%m-%d %H:%M")

            day_info = {
                "day": day,
                "cloud": "cloud01",  # Default unallocated cloud
                "color": self.colors[0],  # Default gray color
                "emoji": None,
                "description": None,
                "owner": None,
                "ticket": None,
            }

            # Check if this day falls within any schedule
            for schedule in schedules:
                if schedule.get("assignment_id") not in self.assignment_colors:
                    self.assignment_colors[schedule.get("assignment_id")] = len(self.assignment_colors) + 1

                chosen_color_idx = self.assignment_colors[schedule.get("assignment_id")]
                schedule_start = datetime.strptime(schedule.get("start").split(".")[0], "%Y-%m-%dT%H:%M:%S")
                schedule_end = datetime.strptime(schedule.get("end").split(".")[0], "%Y-%m-%dT%H:%M:%S")

                if schedule_start <= cell_time <= schedule_end:
                    day_info.update(
                        {
                            "cloud": schedule.get("cloud"),
                            "color": self.colors[chosen_color_idx],
                            "emoji": f"&#{self.emojis[chosen_color_idx]};",
                            "description": schedule.get("description"),
                            "owner": schedule.get("owner"),
                            "ticket": schedule.get("ticket"),
                        }
                    )
                    allocated_count += 1
                    break

            day_data.append(day_info)

        return day_data, allocated_count

    def get_visuals_data(self, when: str) -> Dict[str, Any]:
        """
        Get visuals data for a specific time period.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format

        Returns:
            Dictionary containing visuals data in JSON format
        """
        # Parse the 'when' parameter to determine the target date
        now = datetime.now()

        if when == "current":
            target_date = now
        elif when == "next":
            # Calculate next month
            if now.month == 12:
                target_date = datetime(now.year + 1, 1, 1)
            else:
                target_date = datetime(now.year, now.month + 1, 1)
        else:
            # Parse YYYY-MM format
            try:
                year, month = map(int, when.split("-"))
                target_date = datetime(year, month, 1)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date format: {when}. Use 'current', 'next', or 'YYYY-MM'")

        # Calculate date range for the month
        days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
        first_day = first_day_month(datetime(target_date.year, target_date.month, days_in_month))
        last_day = datetime(target_date.year, target_date.month, days_in_month)

        # Get active hosts (not retired or broken)
        hosts = self._get_active_hosts()

        # Get schedule data for the month
        hosts_schedules = self.api_client.get_monthly_schedules(first_day, last_day)

        # Get current day schedules for daily utilization
        current_schedules = self.api_client.get_current_schedules()

        # Process each host
        host_data = []
        total_allocated = 0

        for host in hosts:
            hostname = host.get("name") if isinstance(host, dict) else host.name
            schedules = hosts_schedules.get(hostname, [])
            days_data, allocated_count = self.process_host_days(
                schedules, days_in_month, target_date.month, target_date.year
            )

            host_data.append({"hostname": hostname, "days": days_data})
            total_allocated += allocated_count

        # Calculate metrics
        total_hosts = len(hosts)
        systems_in_use = len(current_schedules)

        if total_hosts == 0:
            monthly_utilization = 0
            daily_utilization = 0
        else:
            monthly_utilization = (total_allocated * 100) // (days_in_month * total_hosts)
            daily_utilization = (systems_in_use * 100) // total_hosts

        return {
            "title": f"Allocation Map for {target_date.year}-{target_date.month:02d}",
            "metrics": {
                "monthly_utilization": monthly_utilization,
                "daily_utilization": daily_utilization,
                "systems_in_use": systems_in_use,
                "total_systems": total_hosts,
            },
            "hosts": host_data,
        }

    def get_visuals_data_chunked(self, when: str) -> Dict[str, Any]:
        """
        Get visuals data in chunks for progressive loading (legacy method).
        This method is kept for backward compatibility but now uses the new progressive loading approach.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format

        Returns:
            Dictionary containing chunked visuals data optimized for progressive loading
        """
        # Get metadata first
        metadata = self.get_metadata(when)

        # Get host summary
        hosts_summary = self.get_hosts_summary(when)

        # For backward compatibility, load first batch of hosts
        first_batch = self.get_host_batch(when, offset=0, limit=100, priority="mixed")

        # Combine into legacy format
        return {
            "title": metadata["title"],
            "metrics": {
                "monthly_utilization": hosts_summary["summary"]["estimated_monthly_utilization"],
                "daily_utilization": metadata["quick_metrics"]["daily_utilization"],
                "systems_in_use": metadata["quick_metrics"]["systems_in_use"],
                "total_systems": metadata["quick_metrics"]["total_systems"],
            },
            "hosts_summary": {
                "total_hosts": hosts_summary["summary"]["total_hosts"],
                "days_in_month": metadata["date_info"]["days_in_month"],
                "processing_complete": not first_batch["batch_info"]["has_more"],
            },
            "hosts": first_batch["hosts"],
            "loading_info": {
                "chunk_size": metadata["loading_config"]["recommended_chunk_size"],
                "estimated_chunks": metadata["loading_config"]["estimated_chunks"],
                "has_more_batches": first_batch["batch_info"]["has_more"],
                "next_offset": first_batch["batch_info"]["next_offset"],
            },
        }

    def _get_active_hosts(self) -> List[Dict[str, Any]]:
        """Get list of active hosts (not retired or broken)."""
        # Using the API client to get hosts that are not retired or broken
        hosts = self.api_client.get_active_hosts()
        return hosts

    def get_metadata(self, when: str) -> Dict[str, Any]:
        """
        Get fast metadata for immediate UI feedback.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format

        Returns:
            Dictionary containing metadata and quick metrics
        """
        # Check cache first
        cache_key = self._get_cache_key("get_metadata", when)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result

        # Parse date quickly
        target_date = self._parse_when_parameter(when)
        days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]

        # Get host count (fast query)
        hosts = self._get_active_hosts()
        total_hosts = len(hosts)

        # Get current schedules for daily utilization (fast query)
        current_schedules = self.api_client.get_current_schedules()
        systems_in_use = len(current_schedules)

        # Calculate quick metrics
        daily_utilization = (systems_in_use * 100) // total_hosts if total_hosts > 0 else 0

        result = {
            "title": f"Allocation Map for {target_date.year}-{target_date.month:02d}",
            "date_info": {
                "year": target_date.year,
                "month": target_date.month,
                "days_in_month": days_in_month,
                "formatted_date": target_date.strftime("%B %Y"),
            },
            "quick_metrics": {
                "daily_utilization": daily_utilization,
                "systems_in_use": systems_in_use,
                "total_systems": total_hosts,
            },
            "loading_config": {
                "total_hosts": total_hosts,
                "recommended_chunk_size": min(100, max(20, total_hosts // 5)),
                "estimated_chunks": (total_hosts + 99) // 100,  # Ceiling division for 100-host chunks
                "estimated_load_time": min(30, (total_hosts // 100) * 2),  # Rough estimate in seconds
            },
        }

        # Cache the result
        self._set_cache(cache_key, result)
        return result

    def get_hosts_summary(self, when: str) -> Dict[str, Any]:
        """
        Get host list and summary data for table structure.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format

        Returns:
            Dictionary containing host summary and monthly utilization
        """
        target_date = self._parse_when_parameter(when)
        days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
        first_day = first_day_month(datetime(target_date.year, target_date.month, days_in_month))
        last_day = datetime(target_date.year, target_date.month, days_in_month)

        # Get hosts
        hosts = self._get_active_hosts()
        host_names = [host.get("name") if isinstance(host, dict) else host.name for host in hosts]

        # Get basic schedule statistics for monthly utilization
        # This is lighter than processing all individual days
        hosts_schedules = self.api_client.get_monthly_schedules(first_day, last_day)

        # Calculate rough monthly utilization based on schedule coverage
        total_allocated_days = 0
        for hostname in host_names:
            schedules = hosts_schedules.get(hostname, [])
            if schedules:
                # Rough estimate: count schedules (may overlap but gives good approximation)
                total_allocated_days += len(schedules) * days_in_month // 2  # Conservative estimate

        total_possible_days = len(host_names) * days_in_month
        monthly_utilization = (total_allocated_days * 100) // total_possible_days if total_possible_days > 0 else 0

        return {
            "hosts": [{"hostname": hostname, "has_schedules": hostname in hosts_schedules} for hostname in host_names],
            "summary": {
                "total_hosts": len(host_names),
                "days_in_month": days_in_month,
                "hosts_with_schedules": len([h for h in host_names if h in hosts_schedules]),
                "estimated_monthly_utilization": monthly_utilization,
            },
        }

    def get_host_batch(self, when: str, offset: int = 0, limit: int = 100, priority: str = "mixed") -> Dict[str, Any]:
        """
        Get a batch of host allocation data for progressive loading.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format
            offset: Starting host index
            limit: Number of hosts to return (max 100)
            priority: 'allocated' (hosts with schedules first), 'available' (unallocated first), or 'mixed'

        Returns:
            Dictionary containing batch of host allocation data
        """
        # Parse date and get basic info
        target_date = self._parse_when_parameter(when)
        days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
        first_day = first_day_month(datetime(target_date.year, target_date.month, days_in_month))
        last_day = datetime(target_date.year, target_date.month, days_in_month)

        # Limit batch size for performance
        limit = min(limit, 100)

        # Get hosts and schedules with error handling
        try:
            hosts = self._get_active_hosts()
            if not hosts:
                return self._empty_batch_response(offset, limit, priority)
        except Exception as e:
            print(f"Error getting hosts: {e}")
            return self._empty_batch_response(offset, limit, priority, error="Failed to get hosts")

        try:
            hosts_schedules = self.api_client.get_monthly_schedules(first_day, last_day)
        except Exception as e:
            print(f"Error getting schedules: {e}")
            hosts_schedules = {}  # Continue with empty schedules

        # Sort hosts based on priority
        if priority == "allocated":
            # Hosts with schedules first
            hosts.sort(
                key=lambda h: (
                    0 if (h.get("name") if isinstance(h, dict) else h.name) in hosts_schedules else 1,
                    h.get("name") if isinstance(h, dict) else h.name,
                )
            )
        elif priority == "available":
            # Hosts without schedules first
            hosts.sort(
                key=lambda h: (
                    1 if (h.get("name") if isinstance(h, dict) else h.name) in hosts_schedules else 0,
                    h.get("name") if isinstance(h, dict) else h.name,
                )
            )
        else:  # mixed - alphabetical
            hosts.sort(key=lambda h: h.get("name") if isinstance(h, dict) else h.name)

        # Get the requested batch
        batch_hosts = hosts[offset : offset + limit]

        # Process batch hosts
        host_data = []
        batch_allocated = 0

        for host in batch_hosts:
            hostname = host.get("name") if isinstance(host, dict) else host.name
            schedules = hosts_schedules.get(hostname, [])
            days_data, allocated_count = self.process_host_days(
                schedules, days_in_month, target_date.month, target_date.year
            )

            host_data.append({"hostname": hostname, "days": days_data, "allocated_days": allocated_count})
            batch_allocated += allocated_count

        return {
            "batch_info": {
                "offset": offset,
                "limit": limit,
                "returned": len(batch_hosts),
                "total_hosts": len(hosts),
                "has_more": (offset + limit) < len(hosts),
                "next_offset": offset + limit if (offset + limit) < len(hosts) else None,
                "priority": priority,
            },
            "hosts": host_data,
            "batch_stats": {
                "allocated_days_in_batch": batch_allocated,
                "utilization_in_batch": (
                    (batch_allocated * 100) // (len(batch_hosts) * days_in_month) if batch_hosts else 0
                ),
            },
        }

    def _parse_when_parameter(self, when: str) -> datetime:
        """
        Parse the 'when' parameter to get target date.

        Args:
            when: Can be 'current', 'next', or 'YYYY-MM' format

        Returns:
            datetime object for the target month
        """
        now = datetime.now()

        if when == "current":
            return now
        elif when == "next":
            if now.month == 12:
                return datetime(now.year + 1, 1, 1)
            else:
                return datetime(now.year, now.month + 1, 1)
        else:
            try:
                year, month = map(int, when.split("-"))
                return datetime(year, month, 1)
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date format: {when}. Use 'current', 'next', or 'YYYY-MM'")

    def _empty_batch_response(self, offset: int, limit: int, priority: str, error: str = None) -> Dict[str, Any]:
        """Return empty batch response with error information."""
        return {
            "batch_info": {
                "offset": offset,
                "limit": limit,
                "returned": 0,
                "total_hosts": 0,
                "has_more": False,
                "next_offset": None,
                "priority": priority,
                "error": error,
            },
            "hosts": [],
            "batch_stats": {"allocated_days_in_batch": 0, "utilization_in_batch": 0},
        }
