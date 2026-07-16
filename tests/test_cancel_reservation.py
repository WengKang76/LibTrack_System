def active_reservation(
    reservation_id="R001",
    student_id="S001",
    book_id="B002",
    status="Active",
):
    return {
        "reservation_id": reservation_id,
        "student_id": student_id,
        "book_id": book_id,
        "book_title": "Database Systems",
        "reservation_date": "2026-07-13 10:00:00",
        "status": status,
    }


def test_active_reservation_opens_cancellation_confirmation(app_factory):
    app = app_factory(reservations=[active_reservation()])
    client = app.test_client()

    response = client.get("/catalogue/cancel-reservation/R001")
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "Cancel Reservation" in page
    assert "Database Systems" in page
    assert "Confirm Cancellation" in page
    # GET only displays confirmation and must not update Firestore.
    assert fake_db.collections["reservations"][0]["status"] == "Active"


def test_post_cancels_active_reservation(app_factory):
    app = app_factory(reservations=[active_reservation()])
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


def test_cancelled_reservation_cannot_be_cancelled_again(app_factory):
    app = app_factory(
        reservations=[active_reservation(status="Cancelled")]
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
    assert "My Reservations" in page


def test_student_cannot_cancel_another_students_reservation(app_factory):
    app = app_factory(
        reservations=[active_reservation(student_id="S999")]
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


def test_my_reservations_shows_cancel_link_only_for_active_reservations(
    app_factory,
):
    reservations = [
        active_reservation(reservation_id="R001", status="Active"),
        active_reservation(reservation_id="R002", status="Cancelled"),
    ]
    app = app_factory(reservations=reservations)
    client = app.test_client()

    response = client.get("/catalogue/my-reservations")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.count("Cancel Reservation") == 1
    assert "/catalogue/cancel-reservation/R001" in page
    assert "/catalogue/cancel-reservation/R002" not in page


def test_cancel_route_supports_post_not_delete_or_put(app_factory):
    app = app_factory(reservations=[active_reservation()])
    client = app.test_client()

    put_response = client.put("/catalogue/cancel-reservation/R001")
    delete_response = client.delete("/catalogue/cancel-reservation/R001")

    assert put_response.status_code == 405
    assert delete_response.status_code == 405
