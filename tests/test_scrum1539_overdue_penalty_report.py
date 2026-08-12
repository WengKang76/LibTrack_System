"""Acceptance and automated tests for SCRUM-1539."""

from datetime import date
import time

import modules.dashboard_report.repository as dashboard_repository
from modules.dashboard_report.services import build_operational_report


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Overdue Report Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def _mock_students_and_books(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_users",
        lambda: [
            {
                "document_id": "USR001",
                "full_name": "Alicia Tan",
            },
            {
                "document_id": "USR002",
                "full_name": "Daniel Lee",
            },
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_books",
        lambda: [
            {
                "document_id": "BOOK001",
                "title": "Software Engineering",
            },
            {
                "document_id": "BOOK002",
                "title": "Database Systems",
            },
        ],
    )


def test_overdue_report_joins_related_penalty_details(monkeypatch):
    _mock_students_and_books(monkeypatch)
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
                "status": "Borrowed",
            }
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_penalties",
        lambda: [
            {
                "penalty_id": "P001",
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 7.0,
                "status": "Outstanding",
            }
        ],
    )

    result = build_operational_report(
        report_type="overdue",
        today=date(2026, 8, 10),
    )

    assert result["total_records"] == 1
    assert result["total_penalty_amount"] == 7.0
    assert result["penalty_status_totals"] == {"Outstanding": 1}

    record = result["records"][0]
    assert record["student_name"] == "Alicia Tan"
    assert record["book_title"] == "Software Engineering"
    assert record["overdue_days"] == 7
    assert record["penalty_id"] == "P001"
    assert record["penalty_amount"] == 7.0
    assert record["penalty_status"] == "Outstanding"
    assert record["payment_status"] == "Unpaid"
    assert record["payment_method"] == "Not recorded"
    assert record["waiver_status"] == "Not Waived"


def test_overdue_report_shows_paid_and_waived_penalty_states(monkeypatch):
    _mock_students_and_books(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "due_date": "2026-08-01",
                "status": "Borrowed",
            },
            {
                "transaction_id": "BT002",
                "student_id": "USR002",
                "book_id": "BOOK002",
                "due_date": "2026-08-02",
                "status": "Borrowed",
            },
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_penalties",
        lambda: [
            {
                "penalty_id": "P001",
                "transaction_id": "BT001",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 9.0,
                "status": "Paid",
                "payment_method": "Credit Card",
            },
            {
                "penalty_id": "P002",
                "transaction_id": "BT002",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 8.0,
                "status": "Waived",
                "waiver_reason": "Approved medical reason",
            },
        ],
    )

    result = build_operational_report(
        report_type="overdue",
        today=date(2026, 8, 10),
    )
    records = {record["record_id"]: record for record in result["records"]}

    assert records["BT001"]["payment_status"] == "Paid"
    assert records["BT001"]["payment_method"] == "Credit Card"
    assert records["BT001"]["waiver_status"] == "Not Waived"

    assert records["BT002"]["payment_status"] == "Not Applicable"
    assert records["BT002"]["waiver_status"] == "Waived"
    assert records["BT002"]["waiver_reason"] == "Approved medical reason"


def test_overdue_report_handles_transaction_without_penalty(monkeypatch):
    _mock_students_and_books(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT003",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "due_date": "2026-08-01",
                "status": "Borrowed",
            }
        ],
    )
    monkeypatch.setattr(dashboard_repository, "get_all_penalties", lambda: [])

    result = build_operational_report(
        report_type="overdue",
        today=date(2026, 8, 10),
    )

    record = result["records"][0]
    assert record["penalty_id"] == "Not recorded"
    assert record["penalty_amount"] is None
    assert record["penalty_status"] == "Not Recorded"
    assert record["payment_status"] == "Not Recorded"


def test_overdue_penalty_report_page_displays_joined_columns(client, monkeypatch):
    _login_as_librarian(client)
    _mock_students_and_books(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "transaction_id": "BT001",
                "student_id": "USR001",
                "book_id": "BOOK001",
                "due_date": "2026-08-01",
                "status": "Borrowed",
            }
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_penalties",
        lambda: [
            {
                "penalty_id": "P001",
                "transaction_id": "BT001",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 9.0,
                "status": "Outstanding",
            }
        ],
    )

    response = client.get("/librarian/reports?report_type=overdue")

    assert response.status_code == 200
    assert b"Transaction Status" in response.data
    assert b"Penalty Status" in response.data
    assert b"Payment" in response.data
    assert b"Waiver" in response.data
    assert b"Alicia Tan" in response.data
    assert b"Software Engineering" in response.data
    assert b"P001" in response.data
    assert b"RM 9.00" in response.data
