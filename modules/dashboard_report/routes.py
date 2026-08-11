"""Routes for the student and librarian dashboards."""

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from modules.authentication.decorators import (
    librarian_required,
    student_required,
)
from modules.dashboard_report.services import (
    build_librarian_dashboard_statistics,
    build_librarian_pending_actions,
    build_operational_report,
    build_operational_report_csv,
    build_operational_report_filename,
    build_student_attention_alerts,
    build_student_dashboard_summary,
    empty_librarian_pending_actions,
    empty_librarian_statistics,
    empty_operational_report_result,
    empty_student_alerts,
    empty_student_summary,
    get_operational_report_statuses,
    get_operational_report_types,
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
    pending_actions = empty_librarian_pending_actions()
    librarian_dashboard_data_available = True
    pending_actions_available = True

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

    try:
        pending_actions = build_librarian_pending_actions()
    except Exception:
        pending_actions_available = False
        current_app.logger.exception(
            "Failed to load librarian pending-action counts."
        )
        flash(
            "We could not load the latest pending-action summary right now. "
            "Please check the management modules directly.",
            "error",
        )

    return render_template(
        "librarian_dashboard.html",
        statistics=statistics,
        pending_actions=pending_actions,
        librarian_dashboard_data_available=(
            librarian_dashboard_data_available
        ),
        pending_actions_available=pending_actions_available,
    )


@dashboard_bp.route("/librarian/reports")
@librarian_required
def operational_reports():
    """Display validated, read-only operational reports to librarians."""
    filters = {
        "report_type": request.args.get("report_type", "borrowing").strip(),
        "start_date": request.args.get("start_date", "").strip(),
        "end_date": request.args.get("end_date", "").strip(),
        "status": request.args.get("status", "").strip(),
        "book_title": request.args.get("book_title", "").strip(),
    }
    result = empty_operational_report_result(filters["report_type"])
    report_data_available = True

    try:
        result = build_operational_report(**filters)
    except ValueError as error:
        report_data_available = False
        flash(str(error), "error")
    except Exception:
        report_data_available = False
        current_app.logger.exception("Failed to generate an operational report.")
        flash(
            "We could not generate the requested report right now. "
            "Please try again later.",
            "error",
        )

    selected_type = result["report_type"]

    return render_template(
        "dashboard_report/operational_reports.html",
        report=result,
        filters=filters,
        report_types=get_operational_report_types(),
        status_options=get_operational_report_statuses(selected_type),
        report_data_available=report_data_available,
    )


@dashboard_bp.route("/librarian/reports/export")
@librarian_required
def export_operational_report():
    """Export the same validated filters currently used by the report page."""
    filters = {
        "report_type": request.args.get("report_type", "borrowing").strip(),
        "start_date": request.args.get("start_date", "").strip(),
        "end_date": request.args.get("end_date", "").strip(),
        "status": request.args.get("status", "").strip(),
    }
    if filters["report_type"] == "reservation":
        filters["book_title"] = request.args.get("book_title", "").strip()

    try:
        report = build_operational_report(**filters)
        csv_content = build_operational_report_csv(report)
        filename = build_operational_report_filename(report["report_type"])
    except ValueError as error:
        flash(str(error), "error")
        return redirect(
            url_for("dashboard_report.operational_reports", **filters)
        )
    except Exception:
        current_app.logger.exception("Failed to export an operational report.")
        flash(
            "We could not export the requested report right now. "
            "Please try again later.",
            "error",
        )
        return redirect(
            url_for("dashboard_report.operational_reports", **filters)
        )

    response = Response(csv_content, mimetype="text/csv")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
