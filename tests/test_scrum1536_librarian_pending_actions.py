"""Acceptance and automated tests for SCRUM-1536."""

from datetime import date
import time

import modules.dashboard_report.repository as dashboard_repository
import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import build_librarian_pending_actions


def _login_as_librarian(client):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "LIB001"
        user_session["full_name"] = "Pending Action Librarian"
        user_session["role"] = "librarian"
        user_session["last_activity"] = time.time()


def test_librarian_dashboard_displays_pending_action_counts(client, monkeypatch):
    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_dashboard_statistics",
        dashboard_routes.empty_librarian_statistics,
    )
    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_pending_actions",
        lambda: {
            "pending_borrow_requests": 3,
            "pending_returns": 2,
            "pending_renewals": 1,
            "overdue_transactions": 4,
            "unresolved_exceptions": 2,
            "total_pending_actions": 12,
        },
    )

    _login_as_librarian(client)
    response = client.get("/librarian")

    assert response.status_code == 200
    assert b'id="pending-borrow-requests-count">3<' in response.data
    assert b'id="pending-returns-count">2<' in response.data
    assert b'id="pending-renewals-count">1<' in response.data
    assert b'id="overdue-transactions-count">4<' in response.data
    assert b'id="unresolved-exceptions-count">2<' in response.data
    assert b"12 total" in response.data
    assert b'href="/borrowing/"' in response.data


def test_pending_action_service_counts_only_unresolved_records(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_requests",
        lambda: [
            {"status": "Pending"},
            {"status": "Pending Approval"},
            {"status": "Approved"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_all_borrow_transactions",
        lambda: [
            {
                "status": "Return Pending",
                "renewal_status": "None",
                "due_date": "2026-08-10",
            },
            {
                "status": "Borrowed",
                "renewal_status": "Pending",
                "due_date": "2026-08-04",
            },
            {
                "status": "Rejected",
                "return_status": "Rejected",
                "due_date": "2026-08-01",
            },
            {
                "status": "Damaged Exception Recorded",
                "book_exception_status": "Exception Recorded",
                "due_date": "2026-08-01",
            },
            {
                "status": "Closed",
                "book_exception_status": "Exception Recorded",
                "due_date": "2026-08-01",
            },
            {
                "status": "Returned",
                "renewal_status": "Approved",
                "due_date": "2026-07-01",
            },
        ],
    )

    counts = build_librarian_pending_actions(today=date(2026, 8, 6))

    assert counts == {
        "pending_borrow_requests": 2,
        "pending_returns": 1,
        "pending_renewals": 1,
        "overdue_transactions": 1,
        "unresolved_exceptions": 2,
        "total_pending_actions": 7,
    }


def test_pending_action_summary_uses_safe_defaults_when_loading_fails(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_dashboard_statistics",
        dashboard_routes.empty_librarian_statistics,
    )

    def fail_to_load_actions():
        raise RuntimeError("private Firestore pending action detail")

    monkeypatch.setattr(
        dashboard_routes,
        "build_librarian_pending_actions",
        fail_to_load_actions,
    )

    _login_as_librarian(client)
    response = client.get("/librarian")

    assert response.status_code == 200
    assert b"We could not load the latest pending-action summary" in response.data
    assert b"private Firestore pending action detail" not in response.data
    assert b'id="pending-borrow-requests-count">0<' in response.data
    assert b'id="unresolved-exceptions-count">0<' in response.data
