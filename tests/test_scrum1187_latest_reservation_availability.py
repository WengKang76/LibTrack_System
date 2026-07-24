# SCRUM-1187: Retrieve the latest availability before reservation

from modules.catalogue_reservation import routes as catalogue_routes


def _book(**changes):
    book = {
        "book_id": "B001",
        "title": "Distributed Systems",
        "status": "Unavailable",
        "available_copies": 0,
        "total_copies": 2,
        "updated_at": "2026-07-24 10:00:00",
    }
    book.update(changes)
    return book


def test_available_copy_count_overrides_stale_unavailable_status(app_factory):
    app = app_factory(books=[_book(available_copies=1)])
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    reservations = app.extensions["fake_firestore"].collections[
        "reservations"
    ]

    assert response.status_code == 200
    assert "currently available" in page
    assert reservations == []


def test_zero_copy_count_allows_reservation_despite_stale_available_status(
    app_factory,
):
    app = app_factory(
        books=[_book(status="Available", available_copies=0)]
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    reservations = app.extensions["fake_firestore"].collections[
        "reservations"
    ]

    assert response.status_code == 200
    assert len(reservations) == 1
    assert reservations[0]["book_id"] == "B001"
    assert reservations[0]["availability_checked_at"]


def test_reservation_reloads_book_before_database_insert(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_book()])
    client = app.test_client()
    snapshots = [
        (_book(), False),
        (_book(status="Available", available_copies=1), True),
        (_book(status="Available", available_copies=1), True),
    ]

    monkeypatch.setattr(
        catalogue_routes,
        "_load_selected_book",
        lambda _book_id: snapshots.pop(0),
    )

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    reservations = app.extensions["fake_firestore"].collections[
        "reservations"
    ]

    assert response.status_code == 200
    assert "has become available" in page
    assert reservations == []
    assert snapshots == []


def test_missing_book_during_final_reservation_check_creates_no_record(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_book()])
    client = app.test_client()
    snapshots = [(_book(), False), None]

    monkeypatch.setattr(
        catalogue_routes,
        "_load_selected_book",
        lambda _book_id: snapshots.pop(0),
    )

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    reservations = app.extensions["fake_firestore"].collections[
        "reservations"
    ]

    assert response.status_code == 200
    assert "Book not found" in response.get_data(as_text=True)
    assert reservations == []
