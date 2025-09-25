from flask import Blueprint, abort, render_template, Response, jsonify, make_response, request

from quads.web.blueprints.common import WEB_CONTENT_PATH
from quads.web.services.visuals import VisualsService

visual_bp = Blueprint(
    "visual",
    __name__,
    template_folder=WEB_CONTENT_PATH,
)


@visual_bp.route("/")
def index():
    """Show current month visuals by default"""
    return render_template("wiki/visuals.html", when="current")


@visual_bp.route("/<when>")
def visuals(when):
    """
    Render visuals page for a specific time period.
    The actual data will be fetched via JavaScript from the API.
    """
    # Validate the 'when' parameter format
    valid_whens = ["current", "next"]

    # Check if it's a valid YYYY-MM format
    if when not in valid_whens:
        if len(when) == 7 and when[4] == "-":
            try:
                year, month = when.split("-")
                if len(year) == 4 and len(month) == 2:
                    int(year)  # Validate year is numeric
                    month_int = int(month)  # Validate month is numeric
                    if 1 <= month_int <= 12:  # Validate month range
                        valid_whens.append(when)
                    else:
                        return abort(400)  # Invalid month range
                else:
                    return abort(400)  # Invalid format
            except ValueError:
                return abort(400)  # Invalid numeric values
        else:
            return abort(400)  # Invalid format

    # Pass the 'when' parameter to the template - API endpoint is now local to web app
    return render_template("wiki/visuals.html", when=when)


@visual_bp.route("/data/<when>")
def get_visuals_data(when: str) -> Response:
    """
    Get visual allocation data for a specific time period.

    Args:
        when: Can be 'current', 'next', or 'YYYY-MM' format

    Returns:
        JSON response with visual allocation data
    """
    try:
        service = VisualsService()
        data = service.get_visuals_data(when)
        return jsonify(data)

    except ValueError as e:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(e),
        }
        return make_response(jsonify(response), 400)

    except Exception as e:
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": f"An error occurred while generating visuals data: {str(e)}",
        }
        return make_response(jsonify(response), 500)


@visual_bp.route("/data/<when>/metadata")
def get_visuals_metadata(when: str) -> Response:
    """
    Get fast metadata for immediate UI feedback.

    Args:
        when: Can be 'current', 'next', or 'YYYY-MM' format

    Returns:
        JSON response with metadata and quick metrics
    """
    try:
        service = VisualsService()
        data = service.get_metadata(when)
        return jsonify(data)

    except ValueError as e:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(e),
        }
        return make_response(jsonify(response), 400)

    except Exception as e:
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": f"An error occurred while generating metadata: {str(e)}",
        }
        return make_response(jsonify(response), 500)


@visual_bp.route("/data/<when>/hosts")
def get_visuals_hosts_summary(when: str) -> Response:
    """
    Get host list and summary data for table structure.

    Args:
        when: Can be 'current', 'next', or 'YYYY-MM' format

    Returns:
        JSON response with host summary
    """
    try:
        service = VisualsService()
        data = service.get_hosts_summary(when)
        return jsonify(data)

    except ValueError as e:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(e),
        }
        return make_response(jsonify(response), 400)

    except Exception as e:
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": f"An error occurred while generating hosts summary: {str(e)}",
        }
        return make_response(jsonify(response), 500)


@visual_bp.route("/data/<when>/batch")
def get_visuals_host_batch(when: str) -> Response:
    """
    Get a batch of host allocation data for progressive loading.

    Args:
        when: Can be 'current', 'next', or 'YYYY-MM' format

    Query Parameters:
        offset: Starting host index (default: 0)
        limit: Number of hosts to return (default: 100, max: 200)
        priority: 'allocated', 'available', or 'mixed' (default: 'mixed')

    Returns:
        JSON response with batch of host allocation data
    """
    try:
        # Parse query parameters
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 100))
        priority = request.args.get("priority", "mixed")

        # Validate parameters
        if offset < 0:
            raise ValueError("Offset must be non-negative")
        if limit < 1 or limit > 200:
            raise ValueError("Limit must be between 1 and 200")
        if priority not in ["allocated", "available", "mixed"]:
            raise ValueError("Priority must be 'allocated', 'available', or 'mixed'")

        service = VisualsService()
        data = service.get_host_batch(when, offset=offset, limit=limit, priority=priority)
        return jsonify(data)

    except ValueError as e:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(e),
        }
        return make_response(jsonify(response), 400)

    except Exception as e:
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": f"An error occurred while generating host batch: {str(e)}",
        }
        return make_response(jsonify(response), 500)


@visual_bp.route("/data/<when>/chunked")
def get_visuals_data_chunked(when: str) -> Response:
    """
    Get visual allocation data in chunks for progressive loading (legacy endpoint).

    Args:
        when: Can be 'current', 'next', or 'YYYY-MM' format

    Returns:
        JSON response with chunked visual allocation data
    """
    try:
        service = VisualsService()
        data = service.get_visuals_data_chunked(when)
        return jsonify(data)

    except ValueError as e:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": str(e),
        }
        return make_response(jsonify(response), 400)

    except Exception as e:
        response = {
            "status_code": 500,
            "error": "Internal Server Error",
            "message": f"An error occurred while generating chunked visuals data: {str(e)}",
        }
        return make_response(jsonify(response), 500)
