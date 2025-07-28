#!/usr/bin/env python3

import json
import logging
from typing import Dict, Any

from quads.config import Config
from quads.quads_api import QuadsApi


logger = logging.getLogger(__name__)


class ConnectivityDiagram:
    """Generate network connectivity diagrams for QUADS infrastructure"""

    def __init__(self):
        self.quads = QuadsApi(Config)

    def get_network_topology(self) -> Dict[str, Any]:
        """
        Generate network topology data showing how hosts are connected
        through switches and their interfaces.

        Returns:
            Dict containing topology data with hosts, switches, and connections
        """
        topology = {"hosts": [], "switches": {}, "connections": [], "clouds": {}}

        try:
            # Get all hosts with their interfaces
            hosts = self.quads.filter_hosts(data={"retired": False, "broken": False})

            # Track switches and their connections

            for host in hosts:
                host_data = {
                    "id": host.id,
                    "name": host.name,
                    "model": host.model,
                    "cloud": host.cloud.name if host.cloud else "cloud01",
                    "rack": host.rack if hasattr(host, "rack") else None,
                    "interfaces": [],
                }

                # Process host interfaces
                if host.interfaces:
                    for interface in host.interfaces:
                        interface_data = {
                            "name": interface.name,
                            "mac_address": interface.mac_address,
                            "switch_ip": interface.switch_ip,
                            "switch_port": interface.switch_port,
                            "speed": interface.speed,
                            "pxe_boot": interface.pxe_boot,
                        }
                        host_data["interfaces"].append(interface_data)

                        # Track switch connections
                        if interface.switch_ip and interface.switch_port:
                            switch_key = interface.switch_ip
                            if switch_key not in topology["switches"]:
                                topology["switches"][switch_key] = {"ip": interface.switch_ip, "ports": {}}

                            topology["switches"][switch_key]["ports"][interface.switch_port] = {
                                "host": host.name,
                                "interface": interface.name,
                                "mac": interface.mac_address,
                                "speed": interface.speed,
                            }

                            # Create connection entry
                            topology["connections"].append(
                                {
                                    "host": host.name,
                                    "host_interface": interface.name,
                                    "switch_ip": interface.switch_ip,
                                    "switch_port": interface.switch_port,
                                    "mac_address": interface.mac_address,
                                    "cloud": host.cloud.name if host.cloud else "cloud01",
                                }
                            )

                topology["hosts"].append(host_data)

                # Track clouds
                cloud_name = host.cloud.name if host.cloud else "cloud01"
                if cloud_name not in topology["clouds"]:
                    topology["clouds"][cloud_name] = {"name": cloud_name, "hosts": []}
                topology["clouds"][cloud_name]["hosts"].append(host.name)

        except Exception as e:
            logger.error(f"Error generating network topology: {e}")

        return topology

    def get_cloud_connectivity(self, cloud_name: str) -> Dict[str, Any]:
        """
        Get connectivity information for a specific cloud with consolidated connections

        Args:
            cloud_name: Name of the cloud to analyze

        Returns:
            Dict containing cloud-specific connectivity data with consolidated connections
        """
        cloud_topology = {"cloud": cloud_name, "hosts": [], "switches": set(), "connections": []}

        try:
            # Get hosts for this cloud
            cloud_hosts = self.quads.filter_hosts(data={"cloud": cloud_name, "retired": False, "broken": False})

            # Track consolidated connections per host-switch pair
            consolidated_connections = {}

            for host in cloud_hosts:
                host_data = {"name": host.name, "model": host.model, "interfaces": []}

                if host.interfaces:
                    for interface in host.interfaces:
                        interface_data = {
                            "name": interface.name,
                            "switch_ip": interface.switch_ip,
                            "switch_port": interface.switch_port,
                            "mac_address": interface.mac_address,
                            "speed": interface.speed,
                            "pxe_boot": interface.pxe_boot,
                        }
                        host_data["interfaces"].append(interface_data)

                        if interface.switch_ip:
                            cloud_topology["switches"].add(interface.switch_ip)

                            # Consolidate connections by host-switch pair
                            connection_key = f"{host.name}:{interface.switch_ip}"
                            if connection_key not in consolidated_connections:
                                consolidated_connections[connection_key] = {
                                    "host": host.name,
                                    "switch_ip": interface.switch_ip,
                                    "interfaces": [],
                                    "interface_count": 0,
                                }

                            consolidated_connections[connection_key]["interfaces"].append(
                                {
                                    "name": interface.name,
                                    "switch_port": interface.switch_port,
                                    "mac_address": interface.mac_address,
                                    "speed": interface.speed,
                                    "pxe_boot": interface.pxe_boot,
                                }
                            )
                            consolidated_connections[connection_key]["interface_count"] += 1

                cloud_topology["hosts"].append(host_data)

            # Convert consolidated connections to list
            cloud_topology["connections"] = list(consolidated_connections.values())

            # Convert set to list for JSON serialization
            cloud_topology["switches"] = list(cloud_topology["switches"])

        except Exception as e:
            logger.error(f"Error getting cloud connectivity for {cloud_name}: {e}")

        return cloud_topology

    def get_switch_details(self, switch_ip: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific switch and its connections

        Args:
            switch_ip: IP address of the switch

        Returns:
            Dict containing switch details and connected hosts
        """
        switch_details = {"switch_ip": switch_ip, "connected_hosts": [], "port_usage": {}}

        try:
            # Find all interfaces connected to this switch
            hosts = self.quads.filter_hosts(
                data={"interfaces.switch_ip": switch_ip, "retired": False, "broken": False}
            )

            for host in hosts:
                if host.interfaces:
                    for interface in host.interfaces:
                        if interface.switch_ip == switch_ip:
                            host_connection = {
                                "host_name": host.name,
                                "host_cloud": host.cloud.name if host.cloud else "cloud01",
                                "interface_name": interface.name,
                                "switch_port": interface.switch_port,
                                "mac_address": interface.mac_address,
                                "speed": interface.speed,
                            }
                            switch_details["connected_hosts"].append(host_connection)

                            if interface.switch_port:
                                switch_details["port_usage"][interface.switch_port] = {
                                    "host": host.name,
                                    "interface": interface.name,
                                    "cloud": host.cloud.name if host.cloud else "cloud01",
                                }

        except Exception as e:
            logger.error(f"Error getting switch details for {switch_ip}: {e}")

        return switch_details

    def export_topology_json(self) -> str:
        """Export full topology as JSON string"""
        topology = self.get_network_topology()
        return json.dumps(topology, indent=2)

    def get_topology_summary(self) -> Dict[str, Any]:
        """Get a summary overview of the network topology"""
        topology = self.get_network_topology()

        summary = {
            "total_hosts": len(topology["hosts"]),
            "total_switches": len(topology["switches"]),
            "total_connections": len(topology["connections"]),
            "clouds": list(topology["clouds"].keys()),
            "switch_ips": list(topology["switches"].keys()),
        }

        # Count hosts per cloud
        summary["hosts_per_cloud"] = {}
        for cloud_name, cloud_data in topology["clouds"].items():
            summary["hosts_per_cloud"][cloud_name] = len(cloud_data["hosts"])

        return summary


def main():
    """CLI entry point for connectivity diagram tool"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate QUADS connectivity diagrams")
    parser.add_argument("--output", choices=["json", "summary"], default="summary", help="Output format")
    parser.add_argument("--cloud", help="Generate diagram for specific cloud")
    parser.add_argument("--switch", help="Get details for specific switch IP")

    args = parser.parse_args()

    diagram = ConnectivityDiagram()

    if args.switch:
        result = diagram.get_switch_details(args.switch)
    elif args.cloud:
        result = diagram.get_cloud_connectivity(args.cloud)
    elif args.output == "json":
        result = diagram.get_network_topology()
    else:
        result = diagram.get_topology_summary()

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
