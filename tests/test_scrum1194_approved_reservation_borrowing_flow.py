# SCRUM-1194: Continue an approved reservation into Borrowing


def _book(**changes):
    book = {
        "book_id": "B001",
        "title": "Cloud Architecture",
        "author": "Test Author",
        "category": "Computing",
        "status": "Available",
        "available_copies": 1,
        "total_copies": 2,
        "catalogue_status": "Active",
        "is_visible_to_students": True,
        "updated_at": "2026-07-28 09:00:00",
    }
    book.update(changes)
    return book


def _reservation(**changes):
    reservation = {
        "reservation_id": "R001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Cloud Architecture",
        "reservation_date": "2026-07-27 10:00:00",
        "status": "Approved",
    }
    reservation.update(changes)
    return reservation


def test_my_reservations_shows_continue_action_for_approved_record(app_factory):
    app = app_factory(
        books=[_book()],
        reservations=[_reservation()],
    )
    client = app.test_client()

    response = client.get("/catalogue/my-reservations")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Continue to Borrow" in page
    assert "/catalogue/reservation/R001/borrow" in page


def test_approved_reservation_opens_borrow_confirmation(app_factory):
    app = app_factory(
        books=[_book()],
        reservations=[_reservation()],
    )
    client = app.test_client()

    response = client.get("/catalogue/reservation/R001/borrow")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Approved Reservation to Borrowing" in page
    assert "R001" in page
    assert "Cloud Architecture" in page


def test_approved_reservation_creates_linked_borrow_request(app_factory):
    app = app_factory(
        books=[_book()],
        reservations=[_reservation()],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reservation/R001/borrow",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]
    requests = fake_db.collections["borrow_requests"]
    reservation = fake_db.collections["reservations"][0]

    assert response.status_code == 200
    assert len(requests) == 1
    assert requests[0]["student_id"] == "S001"
    assert requests[0]["book_id"] == "B001"
    assert requests[0]["reservation_id"] == "R001"
    assert requests[0]["request_source"] == "Approved Reservation"
    assert requests[0]["status"] == "Pending"
    assert reservation["status"] == "Borrow Request Submitted"
    assert reservation["borrowing_request_id"] == requests[0]["request_id"]


def test_student_cannot_continue_another_students_reservation(app_factory):
    app = app_factory(
        books=[_book()],
        reservations=[_reservation(student_id="S002")],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reservation/R001/borrow",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "do not have permission" in response.get_data(as_text=True)
    assert fake_db.collections["borrow_requests"] == []
    assert fake_db.collections["reservations"][0]["status"] == "Approved"


def test_non_approved_reservation_cannot_continue(app_factory):
    app = app_factory(
        books=[_book()],
        reservations=[_reservation(status="Active")],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reservation/R001/borrow",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Only an approved reservation" in response.get_data(as_text=True)
    assert app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ] == []


def test_unavailable_reserved_book_cannot_continue(app_factory):
    app = app_factory(
        books=[_book(status="Unavailable", available_copies=0)],
        reservations=[_reservation()],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reservation/R001/borrow",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "not currently available" in response.get_data(as_text=True)
    assert app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ] == []
