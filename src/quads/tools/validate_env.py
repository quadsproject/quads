#!/usr/bin/env python3
import asyncio
import logging
from datetime import datetime, timedelta
from socket import gaierror

import yaml
from requests import ConnectionError

from quads.config import Config
from quads.quads_api import APIBadRequest, APIServerException
from quads.quads_api import QuadsApi as Quads
from quads.tools.external.netcat import Netcat
from quads.tools.external.postman import SMTP
from quads.tools.external.ssh import SSHHelper
from quads.tools.external.switch import Switch

logger = logging.getLogger(__name__)

# silence paramiko logging
logging.getLogger("paramiko").setLevel(logging.CRITICAL)

quads = Quads(Config)


async def validate_env(_args, _logger=None):
    if _logger:
        logger = _logger

    _filter = {"active": True, "validated": False, "cloud__ne": "cloud01"}
    assignments = quads.filter_assignments(_filter)
    for _ass in assignments:
        if not _ass.provisioned and _ass.wipe:
            logger.debug(f"Skipping validation for {_ass.cloud.name}: Assignment not marked provisioned.")
            continue

        _schedules = quads.get_current_schedules(data={"cloud": _ass.cloud.name})
        if not _schedules:
            logger.warning(f"No active schedules found for {_ass.cloud.name}")
            continue

        hosts = [s.host for s in _schedules]
        # skip this cloud if we found any retired/broken hosts
        if any(h.retired or h.broken for h in hosts):
            continue

        # skip this cloud if we found any host that hasn't finished building
        if any(not h.build for h in hosts):
            continue

        validation_errors = []

        if not _args.get("skip_hosts"):
            logger.info(f"Validating {_ass.cloud.name}")
            for host in hosts:
                # skip any hosts that are already validated
                if host.validated:
                    continue

                if not _args.get("skip_network"):
                    try:
                        Switch().verify(host.name, _ass.cloud.name)
                    except Exception as e:
                        validation_errors.append(f"{host.name} switch configuration mismatch: {e}")

                if not _args.get("skip_system"):
                    # Check ssh
                    ssh = SSHHelper(host.name)
                    try:
                        await ssh.wait()
                    except (ConnectionError, gaierror, OSError) as e:
                        validation_errors.append(f"{host.name} SSH unreachable: {e}")
                        continue

                    # Check basic system health
                    try:
                        _, stdout, _ = await ssh.command("systemctl is-system-running")
                        status = stdout.strip()
                        if status not in ["running", "degraded"]:
                            validation_errors.append(f"{host.name} system status: {status}")
                    except Exception as e:
                        validation_errors.append(f"{host.name} failed system check: {e}")

        if not validation_errors:
            # All hosts passed validation
            # Update host status
            for host in hosts:
                if not host.validated:
                    quads.update_host(
                        host.name,
                        {"validated": True},
                    )

            # Update assignment status
            quads.update_assignment(
                _ass.id,
                {
                    "validated": True,
                    "notification.initial": False,
                    "notification.pre_initial": False,
                },
            )

            # Send success notification
            if not _ass.notification.success:
                SMTP.notify(
                    _ass.owner,
                    _ass,
                    template="assignment_ready",
                    cc=_ass.ccuser,
                )
                quads.update_notification(_ass.notification.id, {"success": True})

        else:
            # Log errors and potentially notify failure
            for error in validation_errors:
                logger.error(error)

            if not _ass.notification.fail:
                SMTP.notify(
                    Config["quads_admin_email"],
                    _ass,
                    template="validation_failure",
                    errors=validation_errors,
                )
                quads.update_notification(_ass.notification.id, {"fail": True})
