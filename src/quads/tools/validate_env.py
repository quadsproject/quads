#!/usr/bin/env python3
import argparse
import logging

from quads.config import Config
from quads.exceptions import CliException
from quads.quads_api import QuadsApi, APIServerException, APIBadRequest
from quads.plugins.dispatchers.validator import get_validator_dispatcher
from quads.plugins.manager import PluginManager


logger = logging.getLogger(__name__)
quads = QuadsApi(Config)

# Initialize plugin manager and validator dispatcher
plugin_manager = PluginManager()
plugin_manager.initialize()


class Validator(object):  # pragma: no cover
    """Wrapper class to maintain compatibility with existing code"""

    def __init__(self, cloud, assignment, _args):
        self.cloud = cloud
        self.assignment = assignment
        self.report = ""
        self.args = _args
        self.hosts = quads.filter_hosts({"cloud": self.cloud, "validated": False})
        self.hosts = [host for host in self.hosts if quads.get_current_schedules({"host": host.name})]
        self.skip_hosts = self.args.skip_hosts[0] if self.args.skip_hosts else None
        if self.skip_hosts:
            self.hosts = [host for host in self.hosts if host.name not in self.skip_hosts]

        # Get the validator dispatcher
        self.validator_dispatcher = get_validator_dispatcher(plugin_manager)

    async def validate_env(self):
        """Run validation using the validator plugin"""
        success, self.report = await self.validator_dispatcher.validate_env(
            self.cloud,
            self.assignment,
            self.hosts,
            self.args,
            self.report,
        )
        return


async def main(_args, _logger=None):  # pragma: no cover
    global logger
    if _logger:
        logger = _logger

    # start by setting any assignment provisioned flag to true if all hosts are validated
    _filter = {"active": True, "validated": False, "provisioned": False, "cloud__ne": "cloud01"}
    assignments = quads.filter_assignments(_filter)
    for _ass in assignments:
        provisioned = True
        _schedules = quads.get_current_schedules(data={"cloud": _ass.cloud.name})
        for _schedule in _schedules:
            if not _schedule.host.validated:
                provisioned = False
                break
        if provisioned:
            quads.update_assignment(
                _ass.id,
                {
                    "provisioned": True,
                },
            )

    _filter = {"active": True, "validated": False, "provisioned": True, "cloud__ne": "cloud01"}
    assignments = quads.filter_assignments(_filter)

    if type(_args) is dict:
        # Hack for tests to work
        _args = argparse.Namespace(**_args)

    if _args.cloud:
        try:
            quads.get_cloud(_args.cloud)
        except (APIServerException, APIBadRequest) as ex:
            raise CliException(ex)

    if _args.skip_hosts:
        hosts = []
        for hostname in _args.skip_hosts[0]:
            try:
                host = quads.get_host(hostname)
            except (APIServerException, APIBadRequest) as ex:
                raise CliException(ex)
            hosts.append(host)

    for ass in assignments:
        _schedules = quads.get_current_schedules(data={"cloud": ass.cloud.name})
        _schedule_count = len(_schedules)

        _assignment = quads.get_active_cloud_assignment(ass.cloud.name)
        if _schedule_count and _assignment.wipe:
            validator = Validator(ass.cloud.name, _assignment, _args)
            try:
                await validator.validate_env()
            except Exception as ex:
                logger.debug(ex)
                logger.info("Failed validation for %s" % ass.cloud.name)
        elif _schedule_count and not _assignment.wipe:
            logger.info(f"Auto-Validating {ass.cloud.name} as marked for no wipe")
            quads.update_assignment(ass.id, {"validated": True})
