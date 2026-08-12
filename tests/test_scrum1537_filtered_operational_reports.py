"""Acceptance and automated tests for SCRUM-1537."""

from datetime import date
import time

import modules.dashboard_report.repository as dashboard_repository
import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import build_operational_report


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Operational Report Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def _login_as_student(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "STU001"
        user_session["full_name"] = "Student"
        user_session["role"] = "student"
        user_session["last_activity"] = time.time()


def test_operational_report_page_is_librarian_only(client):
    response = client.get("/librarian/reports")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    _login_as_student(client)
    response = client.get("/librarian/reports")
    assert response.status_code == 403


def test_operational_report_filters_borrowing_by_date_and_status(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "STU001",
                "book_id": "BOOK001",
                "borrow_date": "2026-08-01",
                "status": "Borrowed",
            },
            {
                "transaction_id": "BT002",
                "student_id": "STU002",
                "book_id": "BOOK002",
                "borrow_date": "2026-08-04",
                "status": "Returned",
            },
            {
                "transaction_id": "BT003",
                "student_id": "STU003",
                "book_id": "BOOK003",
                "borrow_date": "2026-08-05",
                "status": "Borrowed",
            },
        ],
    )

    result = build_operational_report(
        report_type="borrowing",
        start_date="2026-08-02",
        end_date="2026-08-06",
        status="borrowed",
        today=date(2026, 8, 6),
    )

    assert result["report_title"] == "Borrowing Transactions"
    assert result["total_records"] == 1
    assert result["records"][0]["record_id"] == "BT003"
    assert result["records"][0]["event_date_display"] == "05 Aug 2026"
    assert result["status_totals"] == {"Borrowed": 1}


def test_overdue_report_excludes_returned_and_future_transactions(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "due_date": "2026-08-01",
                "status": "Borrowed",
            },
            {
                "transaction_id": "BT002",
                "due_date": "2026-08-01",
                "status": "Returned",
            },
            {
                "transaction_id": "BT003",
                "due_date": "2026-08-08",
                "status": "Borrowed",
            },
        ],
    )

    result = build_operational_report(
        report_type="overdue",
        today=date(2026, 8, 6),
    )

    assert result["total_records"] == 1
    assert result["records"][0]["record_id"] == "BT001"
    assert result["records"][0]["summary"] == "Overdue by 5 days"


def test_operational_report_page_displays_filtered_results(client, monkeypatch):
    monkeypatch.setattr(
        dashboard_routes,
        "build_operational_report",
        lambda **filters: {
            "report_type": "penalty",
            "report_title": "Penalty Transactions",
            "records": [
                {
                    "record_id": "P001",
                    "event_date": "2026-08-05",
                    "event_date_display": "05 Aug 2026",
                    "status": "Outstanding",
                    "student_id": "STU001",
                    "book_id": "BOOK001",
                    "summary": "Overdue",
                    "amount": 6.5,
                }
            ],
            "total_records": 1,
            "status_totals": {"Outstanding": 1},
        },
    )

    _login_as_librarian(client)
    response = client.get(
        "/librarian/reports?report_type=penalty&status=outstanding"
    )

    assert response.status_code == 200
    assert b"Penalty Transactions" in response.data
    assert b"P001" in response.data
    assert b"STU001" in response.data
    assert b"RM 6.50" in response.data
    assert b"1 matching record found" in response.data


def test_invalid_report_date_range_displays_safe_message(client):
    _login_as_librarian(client)
    response = client.get(
        "/librarian/reports?report_type=borrowing"
        "&start_date=2026-08-10&end_date=2026-08-01"
    )

    assert response.status_code == 200
    assert b"Start date cannot be later than end date" in response.data
    assert b"No report data is shown until the filter issue is resolved" in response.data
