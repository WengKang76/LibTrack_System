# SCRUM-1191: Verify identity and reservation ownership before cancellation


def _reservation(
    reservation_id="R001",
    student_id="S001",
    status="Active",
):
    return {
        "reservation_id": reservation_id,
        "student_id": student_id,
        "book_id": "B001",
        "book_title": "Secure Software Design",
        "reservation_date": "2026-07-27 10:00:00",
        "status": status,
    }


def _flashed_messages(client):
    with client.session_transaction() as session_data:
        return [
            message
            for _category, message
            in session_data.get("_flashes", [])
        ]


def test_logged_out_user_cannot_cancel_reservation(app_factory):
    app = app_factory(
        reservations=[_reservation()],
        authenticated=False,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001"
    )
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 302
    assert stored["status"] == "Active"
    assert "cancellation_date" not in stored
    assert any(
        "Please log in" in message
        for message in _flashed_messages(client)
    )


def test_librarian_cannot_cancel_student_reservation(app_factory):
    app = app_factory(
        reservations=[_reservation()],
        session_user_id="LIB001",
        session_role="librarian",
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001"
    )
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 302
    assert stored["status"] == "Active"
    assert "cancellation_date" not in stored
    assert any(
        "Access denied" in message
        for message in _flashed_messages(client)
    )


def test_student_cannot_cancel_another_students_reservation(app_factory):
    app = app_factory(
        reservations=[_reservation(student_id="S999")],
        session_user_id="S001",
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 200
    assert "Reservation not found." in page
    assert stored["status"] == "Active"
    assert "cancellation_date" not in stored


def test_owner_can_open_confirmation_without_changing_record(app_factory):
    app = app_factory(reservations=[_reservation()])
    client = app.test_client()

    response = client.get(
        "/catalogue/cancel-reservation/R001"
    )
    page = response.get_data(as_text=True)
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 200
    assert "Confirm Cancellation" in page
    assert stored["status"] == "Active"
    assert "cancellation_date" not in stored


def test_owner_can_cancel_active_reservation(app_factory):
    app = app_factory(reservations=[_reservation()])
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 200
    assert "was cancelled successfully" in page
    assert stored["status"] == "Cancelled"
    assert stored["cancellation_date"]
    assert stored["cancelled_by_student_id"] == "S001"


def test_inactive_reservation_cannot_be_cancelled(app_factory):
    app = app_factory(
        reservations=[_reservation(status="Cancelled")]
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    stored = app.extensions["fake_firestore"].collections["reservations"][0]

    assert response.status_code == 200
    assert "Only an active reservation can be cancelled" in page
    assert stored["status"] == "Cancelled"
    assert "cancellation_date" not in stored


def test_missing_reservation_cannot_be_cancelled(app_factory):
    app = app_factory(reservations=[])
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/UNKNOWN",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Reservation not found." in page
