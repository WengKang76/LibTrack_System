"""Acceptance and automated tests for SCRUM-1538."""

from datetime import date
import time

import modules.dashboard_report.repository as dashboard_repository
from modules.dashboard_report.services import build_operational_report


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Borrowing Report Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def _mock_related_records(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_users",
        lambda: [
            {
                "document_id": "USR001",
                "student_id": "24WMR00001",
                "full_name": "Alicia Tan",
            }
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_books",
        lambda: [
            {
                "document_id": "BOOK001",
                "title": "Software Engineering",
            }
        ],
    )


def test_detailed_borrowing_report_joins_student_book_and_dates(monkeypatch):
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "borrow_date": "2026-07-20",
                "due_date": "2026-08-03",
                "return_date": None,
                "renewal_status": "Approved",
                "status": "Borrowed",
            }
        ],
    )

    result = build_operational_report(
        report_type="borrowing",
        today=date(2026, 8, 10),
    )

    assert result["total_records"] == 1
    assert result["overdue_count"] == 1

    record = result["records"][0]
    assert record["record_id"] == "BT001"
    assert record["student_name"] == "Alicia Tan"
    assert record["book_title"] == "Software Engineering"
    assert record["borrow_date_display"] == "20 Jul 2026"
    assert record["due_date_display"] == "03 Aug 2026"
    assert record["return_date_display"] == "Not returned"
    assert record["renewal_status"] == "Approved"
    assert record["is_overdue"] is True
    assert record["overdue_days"] == 7


def test_detailed_borrowing_report_handles_missing_related_records(monkeypatch):
    monkeypatch.setattr(dashboard_repository, "get_all_users", lambda: [])
    monkeypatch.setattr(dashboard_repository, "get_all_books", lambda: [])
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT404",
                "student_id": "MISSING-STUDENT",
                "book_id": "MISSING-BOOK",
                "borrow_date": "2026-08-01",
                "due_date": "2026-08-15",
                "status": "Borrowed",
            }
        ],
    )

    result = build_operational_report(
        report_type="borrowing",
        today=date(2026, 8, 10),
    )

    record = result["records"][0]
    assert record["student_name"] == "Unknown Student"
    assert record["book_title"] == "Unknown Book"
    assert record["return_date_display"] == "Not returned"
    assert record["is_overdue"] is False


def test_detailed_borrowing_report_preserves_existing_filters(monkeypatch):
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "borrow_date": "2026-08-01",
                "due_date": "2026-08-15",
                "status": "Borrowed",
            },
            {
                "transaction_id": "BT002",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "borrow_date": "2026-08-05",
                "due_date": "2026-08-19",
                "return_date": "2026-08-08",
                "status": "Returned",
            },
        ],
    )

    result = build_operational_report(
        report_type="borrowing",
        start_date="2026-08-02",
        end_date="2026-08-10",
        status="returned",
        today=date(2026, 8, 10),
    )

    assert result["total_records"] == 1
    assert result["records"][0]["record_id"] == "BT002"
    assert result["records"][0]["return_date_display"] == "08 Aug 2026"


def test_borrowing_report_page_displays_detailed_columns(client, monkeypatch):
    _login_as_librarian(client)
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "borrow_date": "2026-08-01",
                "due_date": "2026-08-15",
                "return_date": None,
                "renewal_status": "Pending",
                "status": "Borrowed",
            }
        ],
    )

    response = client.get("/librarian/reports?report_type=borrowing")

    assert response.status_code == 200
    assert b"Transaction ID" in response.data
    assert b"Borrow Date" in response.data
    assert b"Due Date" in response.data
    assert b"Return Date" in response.data
    assert b"Renewal" in response.data
    assert b"Alicia Tan" in response.data
    assert b"Software Engineering" in response.data
