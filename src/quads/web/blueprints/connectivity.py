from flask import Blueprint, render_template, jsonify

from quads.web.blueprints.common import WEB_CONTENT_PATH
from quads.tools.connectivity_diagram import ConnectivityDiagram

connectivity_bp = Blueprint(
    "connectivity",
    __name__,
    template_folder=WEB_CONTENT_PATH,
)

diagram_tool = ConnectivityDiagram()


@connectivity_bp.route("/")
async def index():
    """Main connectivity overview page showing all clouds"""
    return render_template("wiki/connectivity_overview.html")


@connectivity_bp.route("/cloud/<cloud_name>")
async def cloud_graph(cloud_name):
    """Individual cloud connectivity graph"""
    return render_template("wiki/connectivity_cloud.html", cloud_name=cloud_name)


@connectivity_bp.route("/topology")
async def topology():
    """Get full network topology data"""
    try:
        topology_data = diagram_tool.get_network_topology()
        return jsonify(topology_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@connectivity_bp.route("/summary")
async def summary():
    """Get topology summary"""
    try:
        summary_data = diagram_tool.get_topology_summary()
        return jsonify(summary_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@connectivity_bp.route("/clouds")
async def clouds_list():
    """Get list of all clouds with basic info"""
    try:
        topology_data = diagram_tool.get_network_topology()
        clouds_info = []

        for cloud_name, cloud_data in topology_data.get("clouds", {}).items():
            host_count = len(cloud_data.get("hosts", []))
            # Count unique switches for this cloud
            switches = set()
            for connection in topology_data.get("connections", []):
                if connection.get("cloud") == cloud_name and connection.get("switch_ip"):
                    switches.add(connection.get("switch_ip"))

            clouds_info.append(
                {
                    "name": cloud_name,
                    "host_count": host_count,
                    "switch_count": len(switches),
                    "hosts": cloud_data.get("hosts", []),
                }
            )

        return jsonify({"clouds": clouds_info})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@connectivity_bp.route("/api/cloud/<cloud_name>")
async def cloud_connectivity_api(cloud_name):
    """Get connectivity data for a specific cloud"""
    try:
        cloud_data = diagram_tool.get_cloud_connectivity(cloud_name)
        return jsonify(cloud_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@connectivity_bp.route("/switch/<switch_ip>")
async def switch_details(switch_ip):
    """Get details for a specific switch"""
    try:
        switch_data = diagram_tool.get_switch_details(switch_ip)
        return jsonify(switch_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@connectivity_bp.route("/export")
async def export_topology():
    """Export topology as JSON"""
    try:
        json_data = diagram_tool.export_topology_json()
        return json_data, 200, {"Content-Type": "application/json"}
    except Exception as e:
        return jsonify({"error": str(e)}), 500
