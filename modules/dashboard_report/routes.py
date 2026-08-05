"""Routes for the student and librarian dashboards."""

from flask import Blueprint, current_app, flash, render_template, session

from modules.authentication.decorators import (
    librarian_required,
    student_required,
)
from modules.dashboard_report.services import (
    build_student_dashboard_summary,
    empty_student_summary,
)


dashboard_bp = Blueprint(
    "dashboard_report",
    __name__,
)


@dashboard_bp.route("/student")
@student_required
def student_dashboard():
    """Display live information for the authenticated student only."""
    student_id = session.get("student_id") or session.get("user_id")
    summary = empty_student_summary()
    dashboard_data_available = True

    try:
        summary = build_student_dashboard_summary(student_id)
    except Exception:
        dashboard_data_available = False
        current_app.logger.exception(
            "Failed to load the authenticated student's dashboard summary."
        )
        flash(
            "We could not load your latest dashboard information right now. "
            "Please try again later.",
            "error",
        )

    return render_template(
        "student_dashboard.html",
        summary=summary,
        dashboard_data_available=dashboard_data_available,
    )


@dashboard_bp.route("/librarian")
@librarian_required
def librarian_dashboard():
    """Display the librarian dashboard to authenticated librarians only."""
    return render_template("librarian_dashboard.html")
