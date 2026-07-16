# SCRUM-689: Reserve an unavailable book


def unavailable_book():
    return {
        "book_id": "B002",
        "title": "Database Systems",
        "author": "Thomas Connolly",
        "category": "Database",
        "status": "Unavailable",
        "available_copies": 0,
    }


def test_unavailable_book_opens_reservation_confirmation(app_factory):
    app = app_factory(books=[unavailable_book()])
    client = app.test_client()

    response = client.get("/catalogue/reserve/B002")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "SCRUM-689" in page
    assert "Confirm Reservation" in page
    assert "Database Systems" in page
    assert 'method="POST"' in page
    assert "Available Copies" in page


def test_post_creates_active_reservation_for_unavailable_book(app_factory):
    app = app_factory(books=[unavailable_book()])
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B002",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]
    reservations = fake_db.collections["reservations"]

    assert response.status_code == 200
    assert "was reserved successfully" in page
    assert len(reservations) == 1
    assert reservations[0]["student_id"] == "S001"
    assert reservations[0]["book_id"] == "B002"
    assert reservations[0]["book_title"] == "Database Systems"
    assert reservations[0]["status"] == "Active"
    assert reservations[0]["reservation_date"]


def test_available_book_cannot_be_reserved(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "status": "Available",
            "available_copies": 2,
        }
    ]
    app = app_factory(books=books)
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "currently available" in page
    assert "Please submit a borrowing request instead" in page
    assert fake_db.collections["reservations"] == []


def test_duplicate_active_reservation_is_prevented(app_factory):
    reservations = [
        {
            "reservation_id": "R001",
            "student_id": "S001",
            "book_id": "B002",
            "book_title": "Database Systems",
            "reservation_date": "2026-07-01 10:00:00",
            "status": "Active",
        }
    ]
    app = app_factory(
        books=[unavailable_book()],
        reservations=reservations,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B002",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "already have an active reservation" in page
    assert len(fake_db.collections["reservations"]) == 1


def test_cancelled_reservation_does_not_block_new_reservation(app_factory):
    reservations = [
        {
            "reservation_id": "R001",
            "student_id": "S001",
            "book_id": "B002",
            "book_title": "Database Systems",
            "reservation_date": "2026-07-01 10:00:00",
            "status": "Cancelled",
        }
    ]
    app = app_factory(
        books=[unavailable_book()],
        reservations=reservations,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B002",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert len(fake_db.collections["reservations"]) == 2
    assert fake_db.collections["reservations"][-1]["status"] == "Active"


def test_zero_copies_allows_reservation_even_if_stored_status_is_available(
    app_factory,
):
    books = [
        {
            "book_id": "B003",
            "title": "Zero Copy Book",
            "status": "Available",
            "available_copies": 0,
        }
    ]
    app = app_factory(books=books)
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B003",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert len(fake_db.collections["reservations"]) == 1
    assert fake_db.collections["reservations"][0]["book_id"] == "B003"


def test_missing_book_cannot_be_reserved(app_factory):
    app = app_factory(books=[])
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/UNKNOWN",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "Book not found." in page
    assert "Book Catalogue" in page
    assert fake_db.collections["reservations"] == []
