"""Routes for the student and librarian dashboards."""

from flask import Blueprint, current_app, flash, render_template, session

from modules.authentication.decorators import (
    librarian_required,
    student_required,
)
from modules.dashboard_report.services import (
    build_librarian_dashboard_statistics,
    build_student_attention_alerts,
    build_student_dashboard_summary,
    empty_librarian_statistics,
    empty_student_alerts,
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
    alerts = empty_student_alerts()
    dashboard_data_available = True
    student_alerts_available = True

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

    try:
        alerts = build_student_attention_alerts(student_id)
    except Exception:
        student_alerts_available = False
        current_app.logger.exception(
            "Failed to load the authenticated student's attention alerts."
        )
        flash(
            "We could not load your attention-required items right now. "
            "Please check the related modules directly.",
            "error",
        )

    return render_template(
        "student_dashboard.html",
        summary=summary,
        alerts=alerts,
        dashboard_data_available=dashboard_data_available,
        student_alerts_available=student_alerts_available,
    )


@dashboard_bp.route("/librarian")
@librarian_required
def librarian_dashboard():
    """Display live read-only library statistics to librarians."""
    statistics = empty_librarian_statistics()
    librarian_dashboard_data_available = True

    try:
        statistics = build_librarian_dashboard_statistics()
    except Exception:
        librarian_dashboard_data_available = False
        current_app.logger.exception(
            "Failed to load librarian dashboard statistics."
        )
        flash(
            "We could not load the latest library statistics right now. "
            "You can still open the management modules below.",
            "error",
        )

    return render_template(
        "librarian_dashboard.html",
        statistics=statistics,
        librarian_dashboard_data_available=(
            librarian_dashboard_data_available
        ),
    )
