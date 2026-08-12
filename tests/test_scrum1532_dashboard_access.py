"""Acceptance and automated tests for SCRUM-1532."""

import time


def _login(client, user_id, role, student_id=None):
    with client.session_transaction() as user_session:
        user_session.clear()
        user_session["user_id"] = user_id
        user_session["student_id"] = student_id or user_id
        user_session["full_name"] = "Dashboard Test User"
        user_session["role"] = role
        user_session["last_activity"] = time.time()


def test_unauthenticated_student_dashboard_redirects_to_login(client):
    response = client.get("/student")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_unauthenticated_librarian_dashboard_redirects_to_login(client):
    response = client.get("/librarian")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_student_cannot_access_librarian_dashboard(client):
    _login(client, "USR001", "student")

    response = client.get("/librarian")

    assert response.status_code == 403
    assert b"Access denied" in response.data


def test_librarian_cannot_access_student_dashboard(client):
    _login(client, "LIB001", "librarian")

    response = client.get("/student")

    assert response.status_code == 403
    assert b"Access denied" in response.data


def test_librarian_can_access_librarian_dashboard(client):
    _login(client, "LIB001", "librarian")

    response = client.get("/librarian")

    assert response.status_code == 200
    assert b"Librarian Dashboard" in response.data
