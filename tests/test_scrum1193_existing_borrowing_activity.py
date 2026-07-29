# SCRUM-1193: Prevent duplicate pending requests and active transactions

from modules.catalogue_reservation import routes as catalogue_routes


def _book():
    return {
        "book_id": "B001",
        "title": "Secure Software Design",
        "author": "Test Author",
        "category": "Computing",
        "status": "Available",
        "available_copies": 2,
        "total_copies": 2,
        "catalogue_status": "Active",
        "is_visible_to_students": True,
    }


def test_pending_borrow_request_prevents_another_request(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_requests=[
            {
                "request_id": "BR001",
                "student_id": "S001",
                "book_id": "B001",
                "status": "Pending",
            }
        ],
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
    assert "already have a pending borrowing request" in (
        response.get_data(as_text=True)
    )
    assert len(requests) == 1


def test_approved_borrow_request_also_prevents_duplicate(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_requests=[
            {
                "request_id": "BR001",
                "student_id": "S001",
                "book_id": "B001",
                "status": "Approved",
            }
        ],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "pending borrowing request" in response.get_data(as_text=True)


def test_active_borrow_transaction_prevents_new_request(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_transactions=[
            {
                "transaction_id": "BT001",
                "student_id": "S001",
                "book_id": "B001",
                "status": "Borrowed",
            }
        ],
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
    assert "already borrowing this book" in response.get_data(as_text=True)
    assert requests == []


def test_return_pending_transaction_remains_active(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_transactions=[
            {
                "transaction_id": "BT001",
                "student_id": "S001",
                "book_id": "B001",
                "status": "Return Pending",
            }
        ],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "already borrowing this book" in response.get_data(as_text=True)


def test_closed_transaction_does_not_prevent_new_request(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_transactions=[
            {
                "transaction_id": "BT001",
                "student_id": "S001",
                "book_id": "B001",
                "status": "Closed",
            }
        ],
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


def test_another_students_transaction_does_not_block_request(app_factory):
    app = app_factory(
        books=[_book()],
        borrow_transactions=[
            {
                "transaction_id": "BT001",
                "student_id": "S002",
                "book_id": "B001",
                "status": "Borrowed",
            }
        ],
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
    assert requests[0]["student_id"] == "S001"


def test_duplicate_activity_is_rechecked_before_insert(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_book()])
    client = app.test_client()
    activity_results = [None, "pending_request"]

    monkeypatch.setattr(
        catalogue_routes,
        "_student_existing_borrowing_activity",
        lambda _student_id, _book_id: activity_results.pop(0),
    )

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]

    assert response.status_code == 200
    assert "pending borrowing request" in response.get_data(as_text=True)
    assert requests == []
    assert activity_results == []
