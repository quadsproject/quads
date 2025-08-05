#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from quads.config import Config, logging_manager
from quads.helpers.utils import is_supported
from quads.quads_api import QuadsApi
from quads.tools.external.badfish import BadfishException, badfish_factory
from quads.tools.external.foreman import Foreman
from quads.tools.external.ipmi import IPMI

logger = logging_manager.get_tool_logger(__name__, level=logging.INFO)
quads = QuadsApi(Config)


async def setup_and_initialize_badfish(host: str, rack: str, uloc: str, blade: str) -> Optional[Any]:
    """Initialize Badfish instance for a host."""
    logger.info(f"Initializing Badfish for {host} (rack: {rack}, uloc: {uloc}, blade: {blade})")

    try:
        badfish = await badfish_factory(
            f"mgmt-{host}",
            rack,
            uloc,
            blade,
            Config["ipmi_username"],
            Config["ipmi_password"],
            propagate=True,
        )
        logger.debug(f"Badfish initialized successfully for {host}")
        return badfish
    except BadfishException as ex:
        logger.error(f"Failed to initialize Badfish for {host}: {ex}")
        logger.error(f"Check IPMI credentials and network access to mgmt-{host}")
        return None


async def prepare_foreman_rebuild(host: str, new_cloud: str, os_type: str, semaphore: asyncio.Semaphore) -> bool:
    """Prepare host for rebuild in Foreman."""
    logger.info(f"Preparing Foreman rebuild for {host} -> {new_cloud} (OS: {os_type})")

    foreman = Foreman(
        Config["foreman_api_url"],
        Config["foreman_username"],
        Config["foreman_password"],
        semaphore=semaphore,
    )
    logger.debug(f"Initialized Foreman client for {host}")

    foreman_results = []

    try:
        logger.debug(f"Fetching available OS types from Foreman for {host}")
        available_os = await foreman.get_available_os()

        os_id = None
        for os in available_os:
            if os["title"] == os_type:
                os_id = os["id"]
                logger.debug(f"Found OS {os_type} with ID {os_id} for {host}")
                break

        if not os_id:
            available_os_names = [os["title"] for os in available_os]
            logger.error(f"OS type '{os_type}' not found in Foreman for {host}")
            logger.error(f"Available OS types: {', '.join(available_os_names)}")
            return False

        params = [{"name": "operatingsystems", "value": os_type, "identifier": "title"}]

        logger.debug(f"Fetching installation media for OS {os_type} for {host}")
        available_mediums = await foreman.get_mediums(os_id)
        if available_mediums:
            params.append({"name": "media", "value": available_mediums[0]["name"]})
            logger.debug(f"Using media: {available_mediums[0]['name']} for {host}")
        else:
            logger.warning(f"No installation media found for OS {os_type} for {host}")

        logger.debug(f"Fetching partition tables for OS {os_type} for {host}")
        available_ptables = await foreman.get_ptables(os_id)
        if available_ptables:
            params.append({"name": "ptables", "value": available_ptables[0]["name"]})
            logger.debug(f"Using partition table: {available_ptables[0]['name']} for {host}")
        else:
            logger.warning(f"No partition tables found for OS {os_type} for {host}")

        logger.debug(f"Setting overcloud parameter for {host}")
        set_result = await foreman.set_host_parameter(host, "overcloud", "true")
        foreman_results.append(set_result)

        logger.debug(f"Setting build flag for {host}")
        put_result = await foreman.put_parameter(host, "build", 1)
        foreman_results.append(put_result)

        logger.debug(f"Setting OS parameters for {host}: {params}")
        put_param_result = await foreman.put_parameters_by_name(host, params)
        foreman_results.append(put_param_result)

        logger.debug(f"Setting owner to {new_cloud} for {host}")
        owner_id = await foreman.get_user_id(new_cloud)
        host_id = await foreman.get_host_id(host)
        put_result = await foreman.put_element("hosts", host_id, "owner_id", owner_id)
        foreman_results.append(put_result)

        logger.debug(f"Owner ID: {owner_id}, Host ID: {host_id} for {host}")

        # Check all Foreman operation results
        failed_operations = []
        for i, result in enumerate(foreman_results):
            if isinstance(result, Exception) or not result:
                failed_operations.append(f"operation_{i}")

        if failed_operations:
            logger.error(f"Foreman setup failed for {host} - failed operations: {', '.join(failed_operations)}")
            return False

        logger.info(f"Foreman rebuild preparation completed successfully for {host}")
        return True
    except Exception as ex:
        logger.error(f"Exception during Foreman setup for {host}: {ex}")
        return False


async def move_and_rebuild(
    host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
) -> bool:  # pragma: no cover
    build_start = datetime.now()
    logger.info(f"=== Starting move and rebuild for {host} -> {new_cloud} (rebuild={rebuild}) ===")
    logger.debug(f"Build start time: {build_start}")

    untouchable_hosts = Config["untouchable_hosts"]
    logger.debug(f"Checking if {host} is in untouchable hosts list: {untouchable_hosts}")

    try:
        _host_obj = quads.get_host(host)
        logger.debug(f"Retrieved host object for {host}: current cloud={_host_obj.cloud.name}")
    except Exception as ex:
        logger.error(f"Failed to get host object for {host}: {ex}")
        return False

    if host in untouchable_hosts:
        logger.error(f"Host {host} is in untouchable hosts list - operation blocked")
        return False

    try:
        _target_cloud = quads.get_cloud(new_cloud)
        logger.debug(f"Retrieved target cloud object: {new_cloud}")
    except Exception as ex:
        logger.error(f"Failed to get cloud object for {new_cloud}: {ex}")
        return False

    ticket = ""
    boot_order = Config.get("foreman_default_boot_order")

    _assignment = quads.get_active_cloud_assignment(_target_cloud.name)
    if _assignment:
        ticket = _assignment.ticket
        logger.info(f"Found active assignment for {new_cloud}: ticket={ticket}, owner={_assignment.owner}")
        if _assignment.boot_order:
            boot_order = _assignment.boot_order
            logger.debug(f"Using custom boot order for {host}: {boot_order}")
    else:
        logger.debug(f"No active assignment found for {new_cloud}")

    ipmi_new_pass = f"{Config['infra_location']}@{ticket}" if ticket else Config["ipmi_password"]
    logger.debug(f"IPMI password pattern for {host}: {'with ticket' if ticket else 'default'}")

    logger.info(f"Configuring IPMI user for {host}")
    ipmi = IPMI(host, Config["ipmi_username"], Config["ipmi_password"], logger=logger)

    try:
        await ipmi.configure_user(Config["ipmi_cloud_username_id"], ipmi_new_pass)
        logger.debug(f"IPMI user configured successfully for {host}")
    except Exception as ex:
        logger.error(f"Failed to configure IPMI user for {host}: {ex}")
        return False

    badfish = None

    if rebuild and _target_cloud.name != _host_obj.default_cloud.name:
        logger.info(
            f"Host {host} requires rebuild (moving from {_host_obj.default_cloud.name} to {_target_cloud.name})"
        )

        if Config.pdu_management:
            logger.debug(f"PDU management enabled for {host} - TODO: implement PDU operations")
            # TODO: pdu management
            pass

        # Initialize Badfish for rebuild operations
        badfish = await setup_and_initialize_badfish(host, _host_obj.rack, _host_obj.uloc, _host_obj.blade)
        if not badfish:
            logger.error(f"Cannot proceed with rebuild for {host} - Badfish initialization failed")
            return False

        # Handle custom boot order if needed
        default_boot_order = Config.get("foreman_default_boot_order")
        if is_supported(host) and boot_order != default_boot_order:
            logger.info(f"Setting custom boot order for {host}: {boot_order} (default: {default_boot_order})")
            try:
                result = await badfish.change_boot(boot_order, Config.get("badfish_interfaces_path"))
                if result:
                    logger.info(f"Boot order change initiated for {host}, waiting 10 minutes for completion")
                    await asyncio.sleep(600)
                    logger.debug(f"Boot order change wait completed for {host}")
                else:
                    logger.warning(f"Boot order change returned False for {host}")
            except BadfishException as ex:
                logger.error(f"Failed to set boot order for {host}: {ex}")
                return False

        # Ensure host is powered on
        logger.info(f"Ensuring {host} is powered on")
        try:
            await badfish.set_power_state("on")
            logger.debug(f"Power state set to ON for {host}")
        except BadfishException as ex:
            logger.error(f"Failed to power on {host}: {ex}")
            return False

        # Determine OS type for rebuild
        os_type = Config["foreman_default_os"]
        if _assignment and _assignment.ostype:
            os_type = _assignment.ostype
            logger.info(f"Using assignment-specific OS type for {host}: {os_type}")
        else:
            logger.debug(f"Using default OS type for {host}: {os_type}")

        # Prepare Foreman for rebuild
        if not await prepare_foreman_rebuild(host, new_cloud, os_type, semaphore):
            logger.error(f"Foreman preparation failed for {host}")
            return False

        # Clean up virtual media
        logger.debug(f"Cleaning up virtual media for {host}")
        try:
            await badfish.unmount_virtual_media()
            logger.debug(f"Virtual media unmounted for {host}")
        except BadfishException as ex:
            logger.warning(f"Could not unmount virtual media for {host}: {ex}")

        try:
            await badfish.detach_remote_image()
            logger.debug(f"Remote image detached for {host}")
        except BadfishException as ex:
            logger.warning(f"Could not detach remote image for {host}: {ex}")

        # Handle reboot for supported hosts
        if is_supported(host):
            logger.info(f"Handling reboot for supported host: {host}")

            # Set boot to default order if it was changed
            if boot_order != Config.get("foreman_default_boot_order"):
                logger.info(f"Resetting boot order to default for {host}")
                try:
                    await badfish.boot_to_type(
                        Config.get("foreman_default_boot_order"),
                        Config.get("badfish_interfaces_path"),
                    )
                    logger.debug(f"Boot order reset to default for {host}")
                except BadfishException as ex:
                    logger.error(f"Failed to set default boot order for {host}: {ex}")
                    return False

            # Perform hard reboot
            logger.info(f"Performing hard reboot for {host}")
            try:
                await badfish.reboot_server(graceful=False)
                logger.info(f"Hard reboot initiated for {host}")
            except BadfishException as ex:
                logger.error(f"Failed to reboot {host}: {ex}")
                return False

        else:
            # Handle unsupported hosts with IPMI
            logger.info(f"Handling reboot for unsupported host {host} via IPMI")
            try:
                await ipmi.pxe_persistent()
                logger.info(f"PXE persistent boot set via IPMI for {host}")
            except Exception as ex:
                logger.error(f"Failed to set PXE boot via IPMI for {host}: {ex}")
                logger.debug(f"IPMI error details for {host}: {ex}")
    else:
        logger.info(
            f"No rebuild required for {host} (rebuild={rebuild}, target_cloud={_target_cloud.name}, default_cloud={_host_obj.default_cloud.name})"
        )

    # Handle returning to default cloud (power off)
    if _target_cloud.name == _host_obj.default_cloud.name:
        logger.info(f"Host {host} is returning to default cloud {_host_obj.default_cloud.name}, powering off")

        if not badfish:
            # Initialize Badfish for power operations
            badfish = await setup_and_initialize_badfish(host, _host_obj.rack, _host_obj.uloc, _host_obj.blade)
            if not badfish:
                logger.error(f"Cannot power off {host} - Badfish initialization failed")
                return False

        try:
            await badfish.set_power_state("off")
            logger.info(f"Host {host} powered off successfully")
        except BadfishException as ex:
            logger.error(f"Failed to power off {host}: {ex}")
            return False

    # Update schedule and host records
    build_end = datetime.now()
    build_duration = build_end - build_start
    logger.info(f"Build operation completed for {host} in {build_duration.total_seconds():.1f} seconds")

    # Update schedule with build times
    data = {"host": _host_obj.name, "cloud": _target_cloud.name}
    schedule = quads.get_current_schedules(data)
    if schedule:
        schedule_data = {
            "build_start": build_start.strftime("%Y-%m-%dT%H:%M"),
            "build_end": build_end.strftime("%Y-%m-%dT%H:%M"),
        }
        try:
            quads.update_schedule(schedule[0].id, schedule_data)
            logger.debug(f"Updated schedule {schedule[0].id} with build times for {host}")
        except Exception as ex:
            logger.error(f"Failed to update schedule for {host}: {ex}")
    else:
        logger.warning(f"No current schedule found for {host} in {_target_cloud.name}")

    # Update host record
    logger.info(f"Updating host record for {host}")
    host_data = {
        "cloud": _target_cloud.name,
        "build": True,
        "last_build": build_end.strftime("%Y-%m-%dT%H:%M"),
        "validated": False,
    }

    try:
        quads.update_host(_host_obj.name, host_data)
        logger.info(f"=== Move and rebuild completed successfully for {host} -> {_target_cloud.name} ====")
        return True
    except Exception as ex:
        logger.error(f"Failed to update host record for {host}: {ex}")
        return False
