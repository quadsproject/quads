from typing import Optional

from quads.helpers.utils import get_vlan
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.config import Config
from quads.quads_api import QuadsApi
from quads.tools.external.switch_cli import SwitchCLI, SwitchCLIException
from quads.plugins.manager import PluginManager


class NetworkSwitchPlugin(SwitchPlugin):
    """
    Generic recipe-driven network switch driver.

    Vendor-specific CLI behavior lives in ``conf/switch_commands.yml``;
    this plugin only contains the non-vendor logic (host/interface
    lookup, VLAN computation, move/modify/verify control flow).  The
    recipe is selected per interface from its ``switch_vendor`` field.
    """

    name = "network"
    version = "1.0.0"
    description = "Generic recipe-driven network switch driver"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.quads = QuadsApi(Config)
        self.recipes = getattr(Config, "vendors", None) or {}
        for vendor, cfg in self.recipes.items():
            # Fail closed at startup on malformed recipes instead of at
            # the first switch operation.
            SwitchCLI(cfg, {}).validate()
        return True

    def _vendor_cfg(self, host: str, interface) -> dict:
        vendor = getattr(interface, "switch_vendor", None)
        if not vendor:
            # Pre-existing interfaces predate switch_vendor; keep the
            # historical Juniper behavior so upgrades keep working.
            vendor = "juniper"
            self.logger.warning(
                "Interface %s on %s has no switch_vendor; assuming historical "
                "'juniper' until the interface is (re)defined",
                interface.name, host,
            )
        cfg = self.recipes.get(vendor)
        if not cfg:
            raise SwitchCLIException(
                f"No switch_commands.yml recipe found for vendor '{vendor}'"
                f" (interface {interface.name} on {host})"
            )
        return cfg

    def _params(self, interface, vendor_cfg) -> dict:
        speed = interface.speed or 0
        username = vendor_cfg.get("username")
        if not username or username == "switch_username":
            # Upgrade path: existing installs carry the switch account in
            # plugins.yml; the shipped recipe only has a placeholder.
            vendor = next(
                (k for k, v in self.recipes.items() if v is vendor_cfg), None
            )
            username = (
                Config.plugins.get(vendor, {}).get("username")
                or Config.plugins.get("juniper", {}).get("username")
            )
            if not username:
                raise SwitchCLIException(
                    f"No switch username configured for vendor '{vendor}'; set "
                    "username in conf/switch_commands.yml"
                )
        return {
            "username": username,
            "switch_ip": interface.switch_ip,
            "switch_port": interface.switch_port,
            # interface.speed is stored in Mbps (--interface-speed docs).
            "speed": speed,
            # EOS 'speed forced' token: speed forced 1000full (1G),
            # speed forced 25gfull (25G), etc.
            "speed_eos": {
                1000: "1000full", 10000: "10gfull", 25000: "25gfull",
                40000: "40gfull", 100000: "100gfull",
            }.get(speed, f"{speed // 1000}gfull"),
        }

    def _get_op(self, host: str, interface, vendor_cfg, params, public: bool, dry_run: bool):
        """Read the current VLAN of an interface via the recipe."""
        ops = vendor_cfg["operations"]
        params = dict(params)
        qinq_op = ops.get("get_vlan_qinq")
        public_op = ops.get("get_vlan_public")
        if not qinq_op or not public_op:
            raise SwitchCLIException(
                f"Recipe for {interface.name} on {host} is missing "
                "get_vlan_qinq/get_vlan_public operations"
            )
        if public:
            value = SwitchCLI(vendor_cfg, params, dry_run).run(public_op)
            if value is None:
                value = SwitchCLI(vendor_cfg, params, dry_run).run(qinq_op)
        else:
            value = SwitchCLI(vendor_cfg, params, dry_run).run(qinq_op)
            if value is None:
                value = SwitchCLI(vendor_cfg, params, dry_run).run(public_op)
        return value

    def _set_op(self, host: str, interface, vendor_cfg, old_vlan, new_vlan, params, dry_run: bool) -> bool:
        ops = vendor_cfg["operations"]
        if old_vlan is None:
            old_vlan = 0
        params = dict(params)
        params["old_vlan"] = int(old_vlan)
        params["new_vlan"] = int(new_vlan)

        # Cloud moves always use dot1q-tunnel (QinQ) so the host's own
        # 802.1Q tags survive; an access-mode port would drop them.
        operation = "set_port_public" if params.get("_public", False) else "set_port_qinq"
        if operation not in ops:
            raise SwitchCLIException(
                f"Recipe for {interface.name} on {host} is missing "
                f"'{operation}' operation"
            )
        try:
            result = SwitchCLI(vendor_cfg, params, dry_run).run(ops[operation])
        except SwitchCLIException as ex:
            self.logger.error(f"Failed to update switch for {host}:{interface.name}: {ex}")
            return False
        if result:
            self.logger.info(f"Successfully updated switch settings for {host}:{interface.name}.")
        else:
            self.logger.error(f"There was something wrong updating switch for {host}:{interface.name}")
        return bool(result)

    def _preflight(self, host, interfaces):
        """Validate every interface's recipe before any switch I/O."""
        prepared = []
        for interface in interfaces:
            vendor_cfg = self._vendor_cfg(host, interface)
            prepared.append((interface, vendor_cfg))
        return prepared

    async def configure(self, host: str, old_cloud: str, new_cloud: str, dry_run: bool = False) -> bool:
        _host_obj = self.quads.get_host(host)
        if not _host_obj:
            self.logger.error("Hostname not found.")
            return False
        if not _host_obj.interfaces:
            self.logger.error("Host has no interfaces defined.")
            return False
        _old_ass_cloud_obj = self.quads.get_active_cloud_assignment(old_cloud)
        _new_ass_cloud_obj = self.quads.get_active_cloud_assignment(new_cloud)
        interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
        try:
            prepared = self._preflight(host, interfaces)
        except SwitchCLIException as ex:
            self.logger.error(str(ex))
            return False
        for (interface, vendor_cfg), i in zip(prepared, range(len(prepared))):
            last_nic = i == len(interfaces) - 1
            params = self._params(interface, vendor_cfg)
            public = bool(_new_ass_cloud_obj and _new_ass_cloud_obj.vlan and last_nic)
            try:
                old_vlan = self._get_op(host, interface, vendor_cfg, params, public, dry_run)
            except SwitchCLIException as ex:
                self.logger.error(f"Failed to read switch for {host}:{interface.name}: {ex}")
                return False
            if old_vlan is None:
                if _new_ass_cloud_obj and not _new_ass_cloud_obj.vlan:
                    self.logger.warning(
                        "Warning: Could not determine the previous VLAN for %s on %s, switch %s, switchport %s"
                        % (host, interface.name, interface.switch_ip, interface.switch_port)
                    )
                old_vlan = get_vlan(_old_ass_cloud_obj, i, last_nic)

            new_vlan = get_vlan(_new_ass_cloud_obj, i, last_nic)

            if _new_ass_cloud_obj and _new_ass_cloud_obj.vlan and last_nic:
                if int(old_vlan) != int(_new_ass_cloud_obj.vlan.vlan_id):
                    self.logger.info("Setting last interface to public vlan %s." % new_vlan)
                    params["_public"] = True
                    if not self._set_op(
                        host, interface, vendor_cfg, old_vlan, _new_ass_cloud_obj.vlan.vlan_id, params, dry_run
                    ):
                        return False
            else:
                if int(old_vlan) != int(new_vlan):
                    params["_public"] = False
                    if not self._set_op(host, interface, vendor_cfg, old_vlan, new_vlan, params, dry_run):
                        return False
        return True

    async def modify(self, host, change=False, overrides=None, dry_run=False):
        overrides = overrides or {}
        _host_obj = self.quads.get_host(host)
        if not _host_obj:
            self.logger.error("Hostname not found.")
            return False
        if not _host_obj.interfaces:
            self.logger.error(f"The host {host} has no interfaces defined")
            return False

        interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
        for index in sorted(overrides.keys()):
            if index >= len(interfaces):
                self.logger.warning(
                    "NIC index %d exceeds host interface count (%d), skipping", index + 1, len(interfaces)
                )
        if not _host_obj.cloud:
            self.logger.error(f"The host {host} has no cloud assigned; cannot compute switch VLANs")
            return False
        _assignment = self.quads.get_active_cloud_assignment(_host_obj.cloud.name)

        try:
            prepared = self._preflight(host, interfaces)
        except SwitchCLIException as ex:
            self.logger.error(str(ex))
            return False
        prepared = {id(interface): vendor_cfg for interface, vendor_cfg in prepared}

        for i, interface in enumerate(interfaces):
            vlan = overrides.get(i)
            if not vlan:
                continue
            vendor_cfg = prepared.get(id(interface))
            if vendor_cfg is None:  # pragma: no cover - prepared covers all
                self.logger.error(f"No recipe found for {interface.name} on {host}")
                return False
            params = self._params(interface, vendor_cfg)
            public = bool(_assignment and _assignment.vlan and i == len(interfaces) - 1)
            try:
                old_vlan = self._get_op(host, interface, vendor_cfg, params, public, dry_run)
            except SwitchCLIException as ex:
                self.logger.error(f"Failed to read switch for {host}:{interface.name}: {ex}")
                return False
            if old_vlan is None:
                old_vlan = 0

            if int(old_vlan) != int(vlan):
                self.logger.warning("Interface %s not configured for vlan%s", interface.switch_port, vlan)
            if change:
                if int(old_vlan) != int(vlan):
                    self.logger.info(f"Change requested for {interface.name}")
                    params["_public"] = public
                    if not self._set_op(host, interface, vendor_cfg, old_vlan, vlan, params, dry_run):
                        return False
                else:
                    self.logger.info(f"Interface {interface.name} is already configured for vlan{vlan}")
            else:
                self.logger.warning(
                    f"Interface {interface.switch_port} appears to be a member of VLAN {old_vlan}, should be {vlan}"
                )
        return True

    async def verify(self, host=None, cloud=None, change=False, dry_run=False):
        all_ok = True
        if not cloud and not host:
            self.logger.warning("At least one of --cloud or --host should be specified.")
            return False
        _cloud_obj = None
        if cloud:
            _cloud = self.quads.get_cloud(cloud)
            if not _cloud:
                self.logger.error("Cloud not found.")
                return False
            _cloud_obj = _cloud
        if host:
            hosts = self.quads.filter_hosts({"name": host, "retired": False})
            if not hosts:
                self.logger.error("Host not found.")
                return False
        else:
            hosts = self.quads.filter_hosts({"cloud": cloud, "retired": False})
            if not hosts:
                self.logger.error("No hosts found on cloud.")
                return False

        first_host = hosts[0]
        if not _cloud_obj:
            _cloud_obj = first_host.cloud
        # Compare names: Cloud objects carry no value equality, and
        # get_cloud/from_dict build different instances every time.
        if _cloud_obj.name != first_host.cloud.name:
            self.logger.warning("Both --cloud and --host have been specified.")
            self.logger.warning(f"Host: {first_host.name}")
            self.logger.warning(f"Cloud: {_cloud_obj.name}")
            self.logger.warning(f"However, {first_host.name} is a member of {first_host.cloud.name}")
            self.logger.warning("!!!!! Be certain this is what you want to do. !!!!!")

        _assignment = self.quads.get_active_cloud_assignment(_cloud_obj.name)
        for _host_obj in hosts:
            self.logger.info(f"Host: {_host_obj.name}")
            if not _host_obj.interfaces:
                self.logger.error(f"Host {_host_obj.name} has no interfaces defined.")
                all_ok = False
                continue
            interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
            for i, interface in enumerate(interfaces):
                last_nic = i == len(interfaces) - 1
                try:
                    vendor_cfg = self._vendor_cfg(_host_obj.name, interface)
                except SwitchCLIException as ex:
                    self.logger.error(str(ex))
                    all_ok = False
                    continue
                params = self._params(interface, vendor_cfg)
                vlan = get_vlan(_assignment, i, last_nic)
                public = bool(_assignment and _assignment.vlan and last_nic)
                try:
                    # Reads are always performed for real: a dry-run verify
                    # must not fabricate VLAN 0 for every interface.
                    vlan_member = self._get_op(_host_obj.name, interface, vendor_cfg, params, public, False)
                except SwitchCLIException as ex:
                    self.logger.error(f"Failed to verify switch for {_host_obj.name}:{interface.name}: {ex}")
                    all_ok = False
                    continue
                if vlan_member is None:
                    vlan_member = 0

                if int(vlan_member) != int(vlan):
                    if not last_nic:
                        self.logger.warning(
                            "Interface %s appears to be a member of VLAN %s, should be %s",
                            interface.switch_port, vlan_member, vlan,
                        )
                    if change:
                        if _assignment and _assignment.vlan and last_nic:
                            if int(_assignment.vlan.vlan_id) != int(vlan_member):
                                self.logger.info(f"Change requested for {interface.name}")
                                self.logger.info(
                                    "Setting last interface to public vlan %s." % _assignment.vlan.vlan_id
                                )
                                params["_public"] = True
                                success = self._set_op(
                                    _host_obj.name, interface, vendor_cfg, vlan_member,
                                    _assignment.vlan.vlan_id, params, dry_run,
                                )
                            else:
                                self.logger.info(f"No changes required for {interface.name}")
                                continue
                        else:
                            self.logger.info(f"Change requested for {interface.name}")
                            params["_public"] = False
                            success = self._set_op(
                                _host_obj.name, interface, vendor_cfg, vlan_member, vlan,
                                params, dry_run,
                            )
                        if success:
                            self.logger.info("Successfully updated switch settings.")
                        else:
                            self.logger.error(f"There was something wrong updating switch for {interface.name}")
                            all_ok = False
                    else:
                        self.logger.error(
                            f"Interface {interface.switch_port} appears to be a member of VLAN {vlan_member}, "
                            f"should be {vlan}"
                        )
                        all_ok = False
        return all_ok

    async def ls_config(self, cloud, all=False):
        all_ok = True
        _assignment = self.quads.get_active_cloud_assignment(cloud)
        if not _assignment:
            self.logger.error("Cloud not found.")
            return False
        self.logger.info(f"Cloud qinq: {_assignment.qinq}")

        hosts = self.quads.filter_hosts({"cloud": cloud})
        if not all:
            hosts = [hosts[0]]

        for host in hosts:
            if all:
                self.logger.info(f"{host.name}:")
            if host and host.interfaces:
                interfaces = sorted(host.interfaces, key=lambda k: k.name)
                for i, interface in enumerate(interfaces):
                    try:
                        vendor_cfg = self._vendor_cfg(host.name, interface)
                    except SwitchCLIException as ex:
                        self.logger.warning(str(ex))
                        all_ok = False
                        continue
                    params = self._params(interface, vendor_cfg)
                    public = bool(_assignment and _assignment.vlan and i == len(interfaces) - 1)
                    try:
                        vlan_member = self._get_op(host.name, interface, vendor_cfg, params, public, False)
                    except SwitchCLIException as ex:
                        self.logger.error(f"Failed to list switch config for {host.name}: {ex}")
                        all_ok = False
                        continue
                    if vlan_member is None:
                        self.logger.warning(
                            "Could not determine the previous VLAN member for %s, switch %s, switch port %s"
                            % (interface.name, interface.switch_ip, interface.switch_port)
                        )
                        vlan_member = 0
                    self.logger.info(
                        f"Interface {interface.name} appears to be a member of VLAN {vlan_member}",
                    )
            else:
                self.logger.error("The cloud has no hosts or the host has no interfaces defined")
                all_ok = False
        return all_ok
