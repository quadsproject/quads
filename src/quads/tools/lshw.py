import os

from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from rich.table import Column

from quads.config import Config
from quads.quads_api import QuadsApi
from quads.tools.external.ssh_helper import SSHHelper

quads = QuadsApi(Config)

LSHW_OUTPUT_DIR = "/opt/quads/lshw/"


def run_lshw(hostname: str, file_path: str) -> None:
    """
    Connect via SSHHElper with the remote host and run lshw command
    :param hostname: the remote host FQDN
    :param file_path: the full file path were the output of lshw is stored
    :return: None
    """
    try:
        ssh_helper = SSHHelper(hostname)
    except Exception:
        print(f"Something went wrong trying to connect to: {hostname}")
        return
    _, output = ssh_helper.run_cmd("lshw -json")
    if output:
        with open(file_path, "w+") as _file:
            for line in output:
                _file.writelines(line)


def main() -> None:
    """
    Main function
    :return: None
    """
    cloud = quads.get_cloud("cloud01")
    hosts = quads.filter_hosts({"cloud": cloud.name, "retired": False, "broken": False})
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}", table_column=Column(min_width=30)),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Collecting lshw", total=len(hosts))
        for host in hosts:
            progress.update(task, description=f"[cyan]{host.name}[/]")
            file_name = f"{host.name}.json"
            file_path = os.path.join(LSHW_OUTPUT_DIR, file_name)
            if os.path.exists(file_path):
                if os.path.getsize(file_path) < 1:
                    run_lshw(host.name, file_path)
            else:
                run_lshw(host.name, file_path)
            progress.advance(task)


if __name__ == "__main__":  # pragma: no cover
    main()
