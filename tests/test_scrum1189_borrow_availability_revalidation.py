# SCRUM-1189: Revalidate availability before borrowing request submission

from modules.catalogue_reservation import routes as catalogue_routes


def _book(**changes):
    book = {
        "book_id": "B001",
        "title": "Cloud Computing",
        "status": "Available",
        "available_copies": 1,
        "total_copies": 3,
        "updated_at": "2026-07-24 12:00:00",
    }
    book.update(changes)
    return book


def test_positive_copy_count_allows_borrow_despite_stale_status(app_factory):
    app = app_factory(
        books=[_book(status="Unavailable", available_copies=1)]
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]

    assert response.status_code == 200
    assert len(requests) == 1
    assert requests[0]["status"] == "Pending"
    assert requests[0]["availability_checked_at"]
    assert requests[0]["book_updated_at"] == "2026-07-24 12:00:00"


def test_zero_copy_count_rejects_borrow_despite_stale_available_status(
    app_factory,
):
    app = app_factory(
        books=[_book(status="Available", available_copies=0)]
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]

    assert response.status_code == 200
    assert "unavailable" in response.get_data(as_text=True).lower()
    assert requests == []


def test_borrow_request_reloads_availability_immediately_before_insert(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_book()])
    client = app.test_client()
    snapshots = [
        (_book(), True),
        (_book(status="Unavailable", available_copies=0), False),
        (_book(status="Unavailable", available_copies=0), False),
    ]

    monkeypatch.setattr(
        catalogue_routes,
        "_load_selected_book",
        lambda _book_id: snapshots.pop(0),
    )

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]

    assert response.status_code == 200
    assert "no longer available" in page
    assert requests == []
    assert snapshots == []


def test_missing_book_during_final_borrow_check_creates_no_request(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_book()])
    client = app.test_client()
    snapshots = [(_book(), True), None]

    monkeypatch.setattr(
        catalogue_routes,
        "_load_selected_book",
        lambda _book_id: snapshots.pop(0),
    )

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]

    assert response.status_code == 200
    assert "Book not found" in response.get_data(as_text=True)
    assert requests == []
