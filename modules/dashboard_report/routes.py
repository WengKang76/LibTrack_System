"""Routes for the student and librarian dashboards."""

from flask import Blueprint, render_template

from modules.authentication.decorators import (
    librarian_required,
    student_required,
)


dashboard_bp = Blueprint(
    "dashboard_report",
    __name__,
)


@dashboard_bp.route("/student")
@student_required
def student_dashboard():
    """Display the student dashboard to authenticated students only."""
    return render_template("student_dashboard.html")


@dashboard_bp.route("/librarian")
@librarian_required
def librarian_dashboard():
    """Display the librarian dashboard to authenticated librarians only."""
    return render_template("librarian_dashboard.html")
