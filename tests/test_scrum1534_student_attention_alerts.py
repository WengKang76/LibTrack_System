"""Acceptance and automated tests for SCRUM-1534."""

import time
from datetime import date

import modules.dashboard_report.repository as dashboard_repository
import modules.dashboard_report.routes as dashboard_routes
from modules.dashboard_report.services import build_student_attention_alerts


def _login_as_student(client, student_id="STU001"):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = "USER-DOC-001"
        user_session["student_id"] = student_id
        user_session["full_name"] = "Student Alert Test"
        user_session["role"] = "student"
        user_session["last_activity"] = time.time()


def test_student_dashboard_displays_attention_items(client, monkeypatch):
    monkeypatch.setattr(
        dashboard_routes,
        "build_student_dashboard_summary",
        lambda student_id: {
            "active_borrowings": 1,
            "active_reservations": 1,
            "pending_borrow_requests": 0,
            "overdue_items": 1,
            "outstanding_penalties": 1,
            "outstanding_penalty_amount": 4.5,
        },
    )
    monkeypatch.setattr(
        dashboard_routes,
        "build_student_attention_alerts",
        lambda student_id: [
            {
                "category": "Overdue Book",
                "title": "Database Systems",
                "message": "This book is overdue.",
                "severity": "danger",
                "action_url": "/catalogue/my-borrowed-books",
                "action_label": "View Borrowed Books",
            },
            {
                "category": "Approved Reservation",
                "title": "Clean Code",
                "message": "Continue into borrowing.",
                "severity": "success",
                "action_url": "/catalogue/my-reservations",
                "action_label": "Continue Reservation",
            },
        ],
    )

    _login_as_student(client)
    response = client.get("/student")

    assert response.status_code == 200
    assert b'id="student-attention-alerts"' in response.data
    assert b"Overdue Book" in response.data
    assert b"Database Systems" in response.data
    assert b"Approved Reservation" in response.data
    assert b"Clean Code" in response.data


def test_attention_builder_returns_only_unresolved_student_items(monkeypatch):
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_borrow_transactions",
        lambda student_id: [
            {
                "student_id": student_id,
                "book_title": "Overdue Book",
                "status": "Borrowed",
                "due_date": "2026-08-03",
            },
            {
                "student_id": student_id,
                "book_title": "Due Tomorrow",
                "status": "Return Pending",
                "due_date": "2026-08-06",
            },
            {
                "student_id": student_id,
                "book_title": "Later Book",
                "status": "Borrowed",
                "due_date": "2026-08-20",
            },
            {
                "student_id": student_id,
                "book_title": "Returned Book",
                "status": "Returned",
                "due_date": "2026-08-01",
            },
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_reservations",
        lambda student_id: [
            {
                "student_id": student_id,
                "book_title": "Approved Book",
                "status": "Approved",
            },
            {
                "student_id": student_id,
                "book_title": "Cancelled Book",
                "status": "Cancelled",
            },
        ],
    )
    monkeypatch.setattr(
        dashboard_repository,
        "get_student_penalties",
        lambda student_id: [
            {
                "student_id": student_id,
                "book_title": "Penalty Book",
                "status": "Outstanding",
                "penalty_amount": 7.5,
            },
            {
                "student_id": student_id,
                "book_title": "Paid Penalty",
                "status": "Paid",
                "penalty_amount": 10,
            },
        ],
    )

    alerts = build_student_attention_alerts(
        "STU001",
        today=date(2026, 8, 5),
        due_soon_days=3,
    )

    assert [alert["category"] for alert in alerts] == [
        "Overdue Book",
        "Due Soon",
        "Approved Reservation",
        "Outstanding Penalty",
    ]
    assert [alert["title"] for alert in alerts] == [
        "Overdue Book",
        "Due Tomorrow",
        "Approved Book",
        "Penalty Book",
    ]
    assert "RM 7.50" in alerts[-1]["message"]


def test_student_dashboard_shows_all_caught_up_when_no_alerts(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard_routes,
        "build_student_dashboard_summary",
        lambda student_id: {
            "active_borrowings": 0,
            "active_reservations": 0,
            "pending_borrow_requests": 0,
            "overdue_items": 0,
            "outstanding_penalties": 0,
            "outstanding_penalty_amount": 0.0,
        },
    )
    monkeypatch.setattr(
        dashboard_routes,
        "build_student_attention_alerts",
        lambda student_id: [],
    )

    _login_as_student(client)
    response = client.get("/student")

    assert response.status_code == 200
    assert b'id="student-no-attention-items"' in response.data
    assert b"You are all caught up" in response.data


def test_student_alert_failure_uses_safe_message(client, monkeypatch):
    monkeypatch.setattr(
        dashboard_routes,
        "build_student_dashboard_summary",
        lambda student_id: {
            "active_borrowings": 0,
            "active_reservations": 0,
            "pending_borrow_requests": 0,
            "overdue_items": 0,
            "outstanding_penalties": 0,
            "outstanding_penalty_amount": 0.0,
        },
    )

    def fail_to_load(student_id):
        raise RuntimeError("private alert database detail")

    monkeypatch.setattr(
        dashboard_routes,
        "build_student_attention_alerts",
        fail_to_load,
    )

    _login_as_student(client)
    response = client.get("/student")

    assert response.status_code == 200
    assert b"We could not load your attention-required items" in response.data
    assert b"private alert database detail" not in response.data
    assert b'id="student-alerts-unavailable"' in response.data
