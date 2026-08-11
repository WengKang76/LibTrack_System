"""Acceptance and automated tests for SCRUM-1540."""

from datetime import date
import csv
from io import StringIO
import time

import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import (
    build_operational_report_csv,
    build_operational_report_filename,
)


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "CSV Report Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def test_csv_export_uses_whitelisted_borrowing_columns_and_safe_values():
    report = {
        "report_type": "borrowing",
        "records": [
            {
                "record_id": "BT001",
                "student_name": "=HYPERLINK(\"bad\",\"Alicia\")",
                "student_id": "S001",
                "book_title": "Software Engineering",
                "book_id": "B001",
                "borrow_date_display": "01 Aug 2026",
                "due_date_display": "15 Aug 2026",
                "return_date_display": "Not returned",
                "renewal_status": "None",
                "status": "Borrowed",
                "email": "private@example.com",
                "password_hash": "must-not-export",
            }
        ],
    }

    csv_text = build_operational_report_csv(report)
    rows = list(csv.reader(StringIO(csv_text)))

    assert rows[0] == [
        "Transaction ID",
        "Student Name",
        "Student ID",
        "Book Title",
        "Book ID",
        "Borrow Date",
        "Due Date",
        "Return Date",
        "Renewal Status",
        "Transaction Status",
    ]
    assert rows[1][0] == "BT001"
    assert rows[1][1].startswith("'=HYPERLINK")
    assert "private@example.com" not in csv_text
    assert "must-not-export" not in csv_text


def test_csv_export_keeps_current_report_filters(client, monkeypatch):
    captured_filters = {}

    def fake_build_report(**filters):
        captured_filters.update(filters)
        return {
            "report_type": "penalty",
            "records": [
                {
                    "record_id": "P001",
                    "event_date_display": "08 Aug 2026",
                    "status": "Outstanding",
                    "student_id": "S001",
                    "book_id": "B001",
                    "summary": "Overdue Penalty",
                    "amount": 6.5,
                }
            ],
        }

    monkeypatch.setattr(dashboard_routes, "build_operational_report", fake_build_report)
    monkeypatch.setattr(
        dashboard_routes,
        "build_operational_report_filename",
        lambda _report_type: "penalty_report_2026-08-10.csv",
    )

    _login_as_librarian(client)
    response = client.get(
        "/librarian/reports/export?report_type=penalty"
        "&start_date=2026-08-01&end_date=2026-08-10&status=outstanding"
    )

    assert response.status_code == 200
    assert captured_filters == {
        "report_type": "penalty",
        "start_date": "2026-08-01",
        "end_date": "2026-08-10",
        "status": "outstanding",
    }
    assert response.mimetype == "text/csv"
    assert "penalty_report_2026-08-10.csv" in response.headers["Content-Disposition"]
    assert b"P001" in response.data
    assert b"6.50" in response.data


def test_csv_export_handles_empty_report_with_headers_only():
    csv_text = build_operational_report_csv(
        {"report_type": "reservation", "records": []}
    )
    rows = list(csv.reader(StringIO(csv_text)))

    assert len(rows) == 1
    assert rows[0] == [
        "Reservation ID",
        "Reservation Date",
        "Reservation Status",
        "Student ID",
        "Book ID",
        "Details",
    ]


def test_csv_filename_contains_report_type_and_export_date():
    filename = build_operational_report_filename(
        "overdue",
        export_date=date(2026, 8, 10),
    )

    assert filename == "overdue_report_2026-08-10.csv"
