"""Acceptance and automated tests for SCRUM-1535."""

import time

import modules.dashboard_report.repository as dashboard_repository
import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import (
    build_librarian_dashboard_statistics,
)


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Librarian Statistics Test"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def test_librarian_dashboard_displays_live_statistics(client, monkeypatch):
    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_dashboard_statistics",
        lambda: {
            "active_students": 12,
            "total_book_titles": 30,
            "total_physical_copies": 75,
            "available_copies": 51,
            "active_borrowings": 14,
            "active_reservations": 6,
            "outstanding_penalties": 4,
            "outstanding_penalty_amount": 22.5,
        },
    )

    _login_as_librarian(client)
    response = client.get("/librarian")

    assert response.status_code == 200
    assert b'id="active-students-count">12<' in response.data
    assert b'id="total-book-titles-count">30<' in response.data
    assert b'id="total-physical-copies-count">75<' in response.data
    assert b'id="available-copies-count">51<' in response.data
    assert b'id="active-borrowings-count">14<' in response.data
    assert b'id="librarian-active-reservations-count">6<' in response.data
    assert b'id="librarian-outstanding-penalties-count">4<' in response.data
    assert b"RM 22.50" in response.data


def test_librarian_statistics_calculate_current_records(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_users",
        lambda: [
            {"role": "Student", "account_status": "Active"},
            {"role": "student", "account_status": ""},
            {"role": "Student", "account_status": "Inactive"},
            {"role": "Librarian", "account_status": "Active"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_books",
        lambda: [
            {"total_copies": 5, "available_copies": 3},
            {"total_copies": "4", "available_copies": "9"},
            {"total_copies": "invalid", "available_copies": -2},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {"status": "Borrowed"},
            {"status": "Return Pending"},
            {"status": "Returned"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_reservations",
        lambda: [
            {"status": "Active"},
            {"status": "Approved"},
            {"status": "Cancelled"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_penalties",
        lambda: [
            {"status": "Outstanding", "penalty_amount": 5},
            {"status": "Unpaid", "penalty_amount": "3.50"},
            {"status": "Paid", "penalty_amount": 10},
        ],
    )

    statistics = build_librarian_dashboard_statistics()

    assert statistics == {
        "active_students": 2,
        "total_book_titles": 3,
        "total_physical_copies": 9,
        "available_copies": 7,
        "active_borrowings": 2,
        "active_reservations": 2,
        "outstanding_penalties": 2,
        "outstanding_penalty_amount": 8.5,
    }


def test_librarian_dashboard_uses_safe_defaults_when_statistics_fail(
    client,
    monkeypatch,
):
    def fail_to_load():
        raise RuntimeError("private statistics database detail")

    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_dashboard_statistics",
        fail_to_load,
    )

    _login_as_librarian(client)
    response = client.get("/librarian")

    assert response.status_code == 200
    assert b"We could not load the latest library statistics" in response.data
    assert b"private statistics database detail" not in response.data
    assert b'id="active-students-count">0<' in response.data
    assert b'id="total-book-titles-count">0<' in response.data
    assert b"RM 0.00" in response.data
    assert b"Library Operations" in response.data
