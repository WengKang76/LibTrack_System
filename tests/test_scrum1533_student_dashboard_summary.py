"""Acceptance and automated tests for SCRUM-1533."""

import time
from datetime import date

import modules.dashboard_report.repository as dashboard_repository
import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import build_student_dashboard_summary


def _login_as_student(client, student_id="STU001"):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "USER-DOC-001"
        user_session["student_id"] = student_id
        user_session["full_name"] = "Student Dashboard Test"
        user_session["role"] = "student"
        user_session["last_activity"] = time.time()


def test_student_dashboard_displays_live_summary_for_session_student(
    client,
    monkeypatch,
):
    captured = {}

    def fake_summary(student_id):
        captured["student_id"] = student_id
        return {
            "active_borrowings": 2,
            "active_reservations": 1,
            "pending_borrow_requests": 3,
            "overdue_items": 1,
            "outstanding_penalties": 2,
            "outstanding_penalty_amount": 12.5,
        }

    monkeypatch.setattr(
        dashboard_routes,
        "build_student_dashboard_summary",
        fake_summary,
    )

    _login_as_student(client, "STU001")
    response = client.get("/student")

    assert response.status_code == 200
    assert captured["student_id"] == "STU001"
    assert b'id="active-borrowings-count">2<' in response.data
    assert b'id="active-reservations-count">1<' in response.data
    assert b'id="pending-borrow-requests-count">3<' in response.data
    assert b'id="overdue-items-count">1<' in response.data
    assert b'id="outstanding-penalties-count">2<' in response.data
    assert b"RM 12.50" in response.data


def test_student_summary_calculates_current_records(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_borrow_transactions",
        lambda student_id: [
            {
                "student_id": student_id,
                "status": "Borrowed",
                "due_date": "2026-08-01",
            },
            {
                "student_id": student_id,
                "status": "Return Pending",
                "due_date": "2026-08-10",
            },
            {
                "student_id": student_id,
                "status": "Returned",
                "due_date": "2026-07-01",
            },
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_reservations",
        lambda student_id: [
            {"student_id": student_id, "status": "Active"},
            {"student_id": student_id, "status": "Cancelled"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_borrow_requests",
        lambda student_id: [
            {"student_id": student_id, "status": "Pending"},
            {"student_id": student_id, "status": "Rejected"},
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_penalties",
        lambda student_id: [
            {
                "student_id": student_id,
                "status": "Outstanding",
                "penalty_amount": 5,
            },
            {
                "student_id": student_id,
                "status": "Unpaid",
                "penalty_amount": "3.50",
            },
            {
                "student_id": student_id,
                "status": "Paid",
                "penalty_amount": 20,
            },
        ],
    )

    summary = build_student_dashboard_summary(
        "STU001",
        today=date(2026, 8, 5),
    )

    assert summary == {
        "active_borrowings": 2,
        "active_reservations": 1,
        "pending_borrow_requests": 1,
        "overdue_items": 1,
        "outstanding_penalties": 2,
        "outstanding_penalty_amount": 8.5,
    }


def test_student_dashboard_shows_safe_defaults_when_data_loading_fails(
    client,
    monkeypatch,
):
    def fail_to_load(student_id):
        raise RuntimeError("private database detail")

    monkeypatch.setattr(
        dashboard_routes,
        "build_student_dashboard_summary",
        fail_to_load,
    )

    _login_as_student(client)
    response = client.get("/student")

    assert response.status_code == 200
    assert b"We could not load your latest dashboard information" in response.data
    assert b"private database detail" not in response.data
    assert b'id="active-borrowings-count">0<' in response.data
    assert b"RM 0.00" in response.data
