import argparse

default_move_command = "/opt/quads/quads/tools/move_and_rebuild.py"

parser = argparse.ArgumentParser(description="Query current cloud for a given host")
action_group = parser.add_mutually_exclusive_group()

# ---- Generic actions

action_group.add_argument(
    "--version",
    dest="action",
    action="store_const",
    const="version",
    help="Display version of QUADS",
)
action_group.add_argument(
    "--mark-broken",
    dest="action",
    action="store_const",
    const="mark_broken",
    help="Mark host as broken",
)
action_group.add_argument(
    "--mark-repaired",
    dest="action",
    action="store_const",
    const="mark_repaired",
    help="Mark broken host as repaired",
)
action_group.add_argument(
    "--retire",
    dest="action",
    action="store_const",
    const="retire",
    help="Mark host as retired",
)
action_group.add_argument(
    "--unretire",
    dest="action",
    action="store_const",
    const="unretire",
    help="Mark retired host as back in business",
)

# ---- Generic args

parser.add_argument(
    "--debug",
    action="store_true",
    default=False,
    help="Show debugging information.",
)
parser.add_argument(
    "--force",
    dest="force",
    action="store_true",
    help="Force host or cloud update when already defined",
)

parser.add_argument(
    "--dry-run",
    dest="dryrun",
    action="store_true",
    default=None,
    help="Don't update state when used with --move-hosts",
)
parser.add_argument(
    "--log-path",
    dest="logpath",
    type=str,
    default=None,
    help="Path to QUADS log file",
)

time_args = parser.add_mutually_exclusive_group()
time_args.add_argument(
    "-d",
    "--date",
    dest="datearg",
    type=str,
    default=None,
    help='date and time to query; e.g. "2016-06-01 08:00"',
)
time_args.add_argument(
    "--months",
    dest="months",
    type=str,
    default=None,
    help="Number of months for reporting scheduled assignments",
)
time_args.add_argument(
    "--year",
    dest="year",
    type=str,
    default=None,
    help="Year for reporting scheduled assignments",
)
time_args.add_argument(
    "--weeks",
    dest="weeks",
    type=str,
    default=None,
    help="Number of weeks to extend an existing schedule",
)
time_args.add_argument(
    "--now",
    dest="now",
    action="store_true",
    default=None,
    help="Now flag for use with --extend or --shrink instead of --week",
)

# ---- Object args

object_args = parser.add_mutually_exclusive_group()
object_args.add_argument(
    "--host",
    dest="host",
    type=str,
    default=None,
    help="Specify the host to query",
)
object_args.add_argument(
    "--host-list",
    dest="host_list",
    type=str,
    default=None,
    help="Specify file path to host list",
)
object_args.add_argument(
    "--cloud",
    dest="cloud",
    type=str,
    default=None,
    help="Specify cloud name",
)

# ---- Advanced actions

action_group.add_argument(
    "--ls-owner",
    dest="action",
    action="store_const",
    const="owner",
    help="List owners",
)
action_group.add_argument(
    "--ls-cc-users",
    dest="action",
    action="store_const",
    const="ccuser",
    help="List CC list",
)
action_group.add_argument(
    "--ls-ticket",
    dest="action",
    action="store_const",
    const="ticket",
    help="List request ticket",
)
action_group.add_argument(
    "--ls-qinq",
    dest="action",
    action="store_const",
    const="qinq",
    help="List cloud qinq state",
)
action_group.add_argument(
    "--ls-wipe",
    dest="action",
    action="store_const",
    const="wipe",
    help="List cloud wipe state",
)
action_group.add_argument(
    "--ls-host-cloud",
    dest="action",
    action="store_const",
    const="host",
    help="Show on what cloud is the host",
)
action_group.add_argument(
    "--extend",
    dest="action",
    action="store_const",
    const="extend",
    help="Extend an existing schedule",
)
action_group.add_argument(
    "--shrink",
    dest="action",
    action="store_const",
    const="shrink",
    help="Shrink an existing schedule",
)
action_group.add_argument(
    "--define-host",
    dest="action",
    action="store_const",
    const="hostresource",
    help="Define a host resource",
)
action_group.add_argument(
    "--define-host-details",
    dest="action",
    action="store_const",
    const="define_host_metadata",
    help="Define a host resource details via yaml",
)
action_group.add_argument(
    "--export-host-details",
    dest="action",
    action="store_const",
    const="host_metadata_export",
    help="Path to QUADS log file",
)
action_group.add_argument(
    "--mod-host",
    dest="action",
    action="store_const",
    const="modhost",
    help="Modify a host",
)
action_group.add_argument(
    "--define-cloud",
    dest="action",
    action="store_const",
    const="cloudresource",
    help="Define a cloud environment",
)
action_group.add_argument(
    "--mod-cloud",
    dest="action",
    action="store_const",
    const="modcloud",
    help="Modify a cloud",
)
action_group.add_argument(
    "--add-schedule",
    dest="action",
    action="store_const",
    const="add_schedule",
    help="Define a host reservation",
)
action_group.add_argument(
    "--mod-schedule",
    dest="action",
    action="store_const",
    const="modschedule",
    help="Modify a host reservation",
)
action_group.add_argument(
    "--add-interface",
    dest="action",
    action="store_const",
    const="addinterface",
    help="Define a host interface",
)
action_group.add_argument(
    "--rm-schedule",
    dest="action",
    action="store_const",
    const="rmschedule",
    help="Remove a host reservation",
)
action_group.add_argument(
    "--rm-interface",
    dest="action",
    action="store_const",
    const="rminterface",
    help="Remove a host interface",
)
action_group.add_argument(
    "--mod-interface",
    dest="action",
    action="store_const",
    const="modinterface",
    help="Modify a host interface",
)
action_group.add_argument(
    "--ls-hosts",
    dest="action",
    action="store_const",
    const="ls_hosts",
    help="List all hosts",
)
action_group.add_argument(
    "--ls-clouds",
    dest="action",
    action="store_const",
    const="ls_clouds",
    help="List all clouds",
)
action_group.add_argument(
    "--rm-host",
    dest="action",
    action="store_const",
    const="rmhost",
    help="Remove a host",
)
action_group.add_argument(
    "--rm-cloud",
    dest="action",
    action="store_const",
    const="rmcloud",
    help="Remove a cloud",
)
action_group.add_argument(
    "--ls-available",
    dest="action",
    action="store_const",
    const="available",
    help="List available hosts on a specific time frame",
)
action_group.add_argument(
    "--ls-schedule",
    dest="action",
    action="store_const",
    const="schedule",
    help="List the host reservations",
)
action_group.add_argument(
    "--ls-interface",
    dest="action",
    action="store_const",
    const="interface",
    help="List the host interfaces",
)
action_group.add_argument(
    "--ls-memory",
    dest="action",
    action="store_const",
    const="memory",
    help="List the host memory",
)
action_group.add_argument(
    "--ls-disks",
    dest="action",
    action="store_const",
    const="disks",
    help="List the host disk",
)
action_group.add_argument(
    "--ls-processors",
    dest="action",
    action="store_const",
    const="processors",
    help="List the host processor",
)
action_group.add_argument(
    "--ls-vlan",
    dest="action",
    action="store_const",
    const="ls_vlan",
    help="List the available vlans with the clouds assigned",
)

action_group.add_argument(
    "--find-free-cloud",
    dest="action",
    action="store_const",
    const="free_cloud",
    help="List available hosts on a specific time frame",
)
action_group.add_argument(
    "--report-available",
    dest="action",
    action="store_const",
    const="report_available",
    help="QUADS reporting server availability",
)
action_group.add_argument(
    "--report-scheduled",
    dest="action",
    action="store_const",
    const="report_scheduled",
    help="QUADS reporting detailed scheduled assignments",
)
action_group.add_argument(
    "--report-detailed",
    dest="action",
    action="store_const",
    const="report_detailed",
    help="QUADS reporting scheduled assignments",
)
action_group.add_argument(
    "--ls-broken",
    dest="action",
    action="store_const",
    const="ls_broken",
    help="List all hosts marked as broken",
)
action_group.add_argument(
    "--ls-retired",
    dest="action",
    action="store_const",
    const="ls_retired",
    help="List all hosts marked as retired",
)

parser.add_argument(
    "--cloud-only",
    dest="action",
    action="store_const",
    const="cloudonly",
    help="Limit full report to hosts only in this cloud",
)
parser.add_argument(
    "--cloud-owner",
    dest="cloudowner",
    type=str,
    default=None,
    help="Define environment owner",
)
parser.add_argument(
    "--cc-users",
    dest="ccusers",
    type=str,
    default=None,
    help="Define environment CC list",
)
parser.add_argument(
    "--qinq",
    dest="qinq",
    type=int,
    choices=[0, 1],
    default=0,
    help="Define environment qinq state",
)

wipe_group_args = parser.add_mutually_exclusive_group()
wipe_group_args.add_argument(
    "--no-wipe",
    dest="wipe",
    default=argparse.SUPPRESS,
    action="store_false",
    help="Define no wipe for safeguarding data after assignment",
)
wipe_group_args.add_argument(
    "--wipe",
    dest="wipe",
    default=argparse.SUPPRESS,
    action="store_true",
    help="Define wipe for reprovisioning server before assignment",
)
parser.add_argument(
    "--cloud-ticket",
    dest="cloudticket",
    type=str,
    default=None,
    help="Define environment ticket",
)
parser.add_argument(
    "--description",
    dest="description",
    type=str,
    default=None,
    help="Define description of cloud",
)
parser.add_argument(
    "--default-cloud",
    dest="defaultcloud",
    type=str,
    default=None,
    help="Define default cloud for a host",
)
parser.add_argument(
    "--model",
    dest="model",
    type=str,
    default=None,
    help="Define host model",
)
parser.add_argument(
    "--summary",
    dest="action",
    action="store_const",
    const="summary",
    help="Generate a summary report",
)
parser.add_argument(
    "--detail",
    dest="detail",
    action="store_true",
    help="Get additional data over the summary",
)
parser.add_argument(
    "--all",
    dest="all",
    action="store_true",
    help="Get all hosts data over the summary",
)
parser.add_argument(
    "--schedule-id",
    dest="schedid",
    type=int,
    default=None,
    help="Schedule id",
)
parser.add_argument(
    "--schedule-start",
    dest="schedstart",
    type=str,
    default=None,
    help="Schedule start date/time",
)
parser.add_argument(
    "--schedule-end",
    dest="schedend",
    type=str,
    default=None,
    help="Schedule end date/time",
)
parser.add_argument(
    "--omit-cloud",
    dest="omitcloud",
    type=str,
    default="",
    help="Specify a cloud from which hosts should be omitted when adding schedule or when listing available.",
)
parser.add_argument(
    "--check",
    dest="check",
    action="store_true",
    default=None,
    help="Check for cloud extension",
)
parser.add_argument(
    "--schedule-cloud",
    dest="schedcloud",
    type=str,
    default=None,
    help="Schedule cloud",
)
parser.add_argument(
    "--interface-name",
    dest="ifname",
    type=str,
    default=None,
    help="Interface name",
)
parser.add_argument(
    "--interface-bios-id",
    dest="ifbiosid",
    type=str,
    default=None,
    help="Interface BIOS ID name",
)
parser.add_argument(
    "--interface-mac",
    dest="ifmac",
    type=str,
    default=None,
    help="Interface MAC address",
)
parser.add_argument(
    "--interface-switch-ip",
    dest="ifip",
    type=str,
    default=None,
    help="Interface IP address",
)
parser.add_argument(
    "--interface-port",
    dest="ifport",
    type=str,
    default=None,
    help="Switch port",
)
parser.add_argument(
    "--interface-speed",
    dest="ifspeed",
    type=str,
    default=None,
    help="Interface speed",
)
parser.add_argument(
    "--interface-vendor",
    dest="ifvendor",
    type=str,
    default=None,
    help="Interface vendor",
)

pxe_group_args = parser.add_mutually_exclusive_group()
pxe_group_args.add_argument(
    "--pxe-boot",
    dest="ifpxe",
    action="store_true",
    default=argparse.SUPPRESS,
    help="Interface pxe boot flag",
)
pxe_group_args.add_argument(
    "--no-pxe-boot",
    dest="ifpxe",
    action="store_false",
    default=argparse.SUPPRESS,
    help="Disable Interface pxe boot flag",
)

maintenance_group_args = parser.add_mutually_exclusive_group()
maintenance_group_args.add_argument(
    "--maintenance",
    dest="ifmaintenance",
    action="store_true",
    default=argparse.SUPPRESS,
    help="Interface maintenance flag",
)
maintenance_group_args.add_argument(
    "--no-maintenance",
    dest="ifmaintenance",
    action="store_false",
    default=argparse.SUPPRESS,
    help="Disable Interface maintenance flag",
)

parser.add_argument(
    "--move-hosts",
    dest="action",
    action="store_const",
    const="movehosts",
    help="Move hosts if schedule has changed",
)
parser.add_argument(
    "--move-command",
    dest="movecommand",
    type=str,
    default=default_move_command,
    help="External command to move a host",
)

parser.add_argument(
    "--host-type",
    dest="hosttype",
    type=str,
    default=None,
    help="Open-ended identifier for host: util, baremetal, aws, openstack, libvirt, etc.",
)
parser.add_argument(
    "--build",
    dest="build",
    type=str,
    choices=["true", "false"],
    default=None,
    help="Whether the host has been built (true/false)",
)
parser.add_argument(
    "--validated",
    dest="validated",
    type=str,
    choices=["true", "false"],
    default=None,
    help="Whether the host has been validated (true/false)",
)
parser.add_argument(
    "--switch-config-applied",
    dest="switchconfigapplied",
    type=str,
    choices=["true", "false"],
    default=None,
    help="Whether the switch config has been applied (true/false)",
)
parser.add_argument(
    "--can-self-schedule",
    dest="canselfschedule",
    type=str,
    choices=["true", "false"],
    default=None,
    help="Whether the host can self-schedule (true/false)",
)
parser.add_argument(
    "--vlan",
    dest="vlan",
    default=None,
    help="VLAN id number for public routable network",
)
parser.add_argument(
    "--metadata",
    dest="metadata",
    type=str,
    default=None,
    help="Path to yml with hosts metadata",
)
parser.add_argument(
    "--filter",
    dest="filter",
    type=str,
    default=None,
    help="Filter search by host metadata",
)
action_group.add_argument(
    "--regen-instack",
    dest="action",
    action="store_const",
    const="regen_instack",
    help="Regenerate instack JSON",
)
action_group.add_argument(
    "--regen-heatmap",
    dest="action",
    action="store_const",
    const="regen_heatmap",
    help="Regenerate web table heatmap",
)
action_group.add_argument(
    "--foreman-rbac",
    dest="action",
    action="store_const",
    const="foreman_rbac",
    help="Regenerate foreman RBAC",
)
action_group.add_argument(
    "--notify",
    dest="action",
    action="store_const",
    const="notify",
    help="Send notifications for cloud assignments",
)
action_group.add_argument(
    "--validate-env",
    dest="action",
    action="store_const",
    const="validate_env",
    help="Validate Quads assignments",
)
parser.add_argument(
    "--skip-system",
    dest="skip_system",
    action="store_true",
    default=False,
    help="Skip system tests, when validating Quads assignments",
)
parser.add_argument(
    "--skip-network",
    dest="skip_network  ",
    action="store_true",
    default=False,
    help="Skip network tests, when validating Quads assignments",
)
parser.add_argument(
    "--skip-hosts",
    dest="skip_hosts",
    action="append",
    nargs="*",
    help="Skip specific hosts, when validating Quads assignments",
)
parser.add_argument(
    "--ls-notifications",
    dest="action",
    action="store_const",
    const="list_notifications",
    help="List notifications",
)
parser.add_argument(
    "--mod-notification",
    dest="action",
    action="store_const",
    const="modify_notification",
    help="Modify notification of a cloud",
)

parser.add_argument(
    "--rack",
    dest="rack",
    type=str,
    default=None,
    help="rack name of the host",
)

parser.add_argument(
    "--blade",
    dest="blade",
    type=str,
    default=None,
    help="blade name of the host",
)

parser.add_argument(
    "--uloc",
    dest="uloc",
    type=str,
    default=None,
    help="U-location name of the host",
)

mod_notification_arg_names = [
    "fail",
    "success",
    "initial",
    "pre-initial",
    "pre",
    "one-day",
    "three-days",
    "five-days",
    "seven-days",
]


def str_to_bool(value):
    """Convert string to boolean."""
    if value.lower() in {"true", "yes", "1"}:
        return True
    elif value.lower() in {"false", "no", "0"}:
        return False
    else:
        raise argparse.ArgumentTypeError(f"Invalid value: {value}. Expected 'true' or 'false'.")


for arg in mod_notification_arg_names:
    parser.add_argument(f"--{arg}", type=str_to_bool, choices=[True, False], help=f"Set {arg} to true or false.")

# --os-list allows to list the operating systems
action_group.add_argument(
    "--os-list",
    dest="action",
    action="store_const",
    const="os_list",
    help="Lists the available operating system",
)

parser.add_argument(
    "--os",
    dest="os",
    default=None,
    help="OS Platform for Provisioning, to list available os --os-list",
)


if __name__ == "__main__":  # pragma: no cover
    # debugging helper
    parser.print_help()
