from flask import Blueprint, redirect, render_template, url_for

from modules.borrowing.services import (
    approve_borrow_request,
    get_all_pending_requests,
)

borrowing_bp = Blueprint(
    "borrowing",
    __name__,
    url_prefix="/borrowing",
)


@borrowing_bp.route("/")
def borrowing_home():
    requests = get_all_pending_requests()

    return render_template(
        "borrowing/index.html",
        requests=requests,
    )


@borrowing_bp.route("/approve/<int:request_id>", methods=["POST"])
def approve_request(request_id: int):
    success = approve_borrow_request(request_id)

    if not success:
        return "Invalid borrow request", 400

    return redirect(url_for("borrowing.borrowing_home"))
