from flask import Blueprint, Response, jsonify, request

from server.dao.report import ReportDao

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/detailed/")
def get_detailed() -> Response:
    """
    Gets a detailed report.

    :param start: str: A date in the past for a time-bound summary
    :param end: str: A date in the past for a time-bound summary
    :return: A response object with a 200 status code
    """

    data = request.args.to_dict()
    _start = data.get("start")
    _end = data.get("end")

    details = ReportDao.get_detailed(_start, _end)

    return jsonify(details)
