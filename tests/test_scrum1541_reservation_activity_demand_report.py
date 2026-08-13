"""Acceptance and automated tests for SCRUM-1541."""

import time

import modules.dashboard_report.repository as dashboard_repository
from modules.dashboard_report.services import build_operational_report


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Reservation Report Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def _mock_related_records(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_users",
        lambda: [
            {"document_id": "S001", "full_name": "Alicia Tan"},
            {"document_id": "S002", "full_name": "Daniel Lee"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_books",
        lambda: [
            {"document_id": "B001", "title": "Software Engineering"},
            {"document_id": "B002", "title": "Database Systems"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_requests",
        lambda: [
            {
                "document_id": "BR001",
                "reservation_id": "R001",
                "status": "Pending",
            }
        ],
    )


def test_reservation_report_joins_related_records_and_ranks_demand(monkeypatch):
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_reservations",
        lambda: [
            {
                "document_id": "R001",
                "student_id": "S001",
                "book_id": "B001",
                "reservation_date": "2026-08-01",
                "status": "Borrow Request Submitted",
                "borrowing_request_id": "BR001",
            },
            {
                "document_id": "R002",
                "student_id": "S002",
                "book_id": "B001",
                "reservation_date": "2026-08-02",
                "status": "Active",
            },
            {
                "document_id": "R003",
                "student_id": "S001",
                "book_id": "B002",
                "reservation_date": "2026-08-03",
                "status": "Cancelled",
            },
        ],
    )

    result = build_operational_report(report_type="reservation")

    assert result["total_records"] == 3
    assert result["status_totals"] == {
        "Cancelled": 1,
        "Active": 1,
        "Borrow Request Submitted": 1,
    }
    assert result["book_demand"][0] == {
        "book_id": "B001",
        "book_title": "Software Engineering",
        "reservation_count": 2,
    }

    records = {record["record_id"]: record for record in result["records"]}
    assert records["R001"]["student_name"] == "Alicia Tan"
    assert records["R001"]["book_title"] == "Software Engineering"
    assert records["R001"]["reservation_date_display"] == "01 Aug 2026"
    assert records["R001"]["borrowing_request_id"] == "BR001"
    assert records["R001"]["borrowing_request_status"] == "Pending"


def test_reservation_report_filters_by_book_title_and_handles_missing_records(monkeypatch):
    monkeypatch.setattr(dashboard_repository, "get_all_users", lambda: [])
    monkeypatch.setattr(dashboard_repository, "get_all_books", lambda: [])
    monkeypatch.setattr(dashboard_repository, "get_all_borrow_requests", lambda: [])
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_reservations",
        lambda: [
            {
                "document_id": "R001",
                "student_id": "S999",
                "book_id": "B999",
                "book_title": "Clean Code",
                "reservation_date": "2026-08-05",
                "status": "Approved",
            },
            {
                "document_id": "R002",
                "student_id": "S998",
                "book_id": "B998",
                "book_title": "Database Systems",
                "reservation_date": "2026-08-06",
                "status": "Approved",
            },
        ],
    )

    result = build_operational_report(
        report_type="reservation",
        status="approved",
        book_title="clean",
    )

    assert result["total_records"] == 1
    record = result["records"][0]
    assert record["record_id"] == "R001"
    assert record["student_name"] == "Unknown Student"
    assert record["book_title"] == "Clean Code"
    assert record["borrowing_request_id"] == "Not submitted"
    assert record["borrowing_request_status"] == "Not submitted"


def test_reservation_report_finds_borrow_request_using_reservation_id(monkeypatch):
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_reservations",
        lambda: [
            {
                "document_id": "R001",
                "student_id": "S001",
                "book_id": "B001",
                "reservation_date": "2026-08-01",
                "status": "Borrow Request Submitted",
            }
        ],
    )

    result = build_operational_report(report_type="reservation")
    record = result["records"][0]

    assert record["borrowing_request_id"] == "BR001"
    assert record["borrowing_request_status"] == "Pending"


def test_reservation_report_page_displays_detailed_columns_and_demand(client, monkeypatch):
    _login_as_librarian(client)
    _mock_related_records(monkeypatch)
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_reservations",
        lambda: [
            {
                "document_id": "R001",
                "student_id": "S001",
                "book_id": "B001",
                "reservation_date": "2026-08-01",
                "status": "Borrow Request Submitted",
                "borrowing_request_id": "BR001",
            }
        ],
    )

    response = client.get(
        "/librarian/reports?report_type=reservation&book_title=Software"
    )

    assert response.status_code == 200
    assert b"Reservation ID" in response.data
    assert b"Related Borrow Request" in response.data
    assert b"Most Requested Books" in response.data
    assert b"Alicia Tan" in response.data
    assert b"Software Engineering" in response.data
    assert b"BR001" in response.data
    assert b"1 reservation" in response.data
