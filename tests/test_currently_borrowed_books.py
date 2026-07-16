from datetime import date

from modules.catalogue_reservation import routes as catalogue_routes


def _approved_request(**overrides):
    record = {
        "request_id": "BR001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Clean Code",
        "request_date": "2026-07-01 10:00:00",
        "borrowing_period": "14 days",
        "borrowing_period_days": 14,
        "status": "Approved",
    }
    record.update(overrides)
    return record


def test_currently_borrowed_books_route_returns_success(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Currently Borrowed Books" in page
    assert "No currently borrowed books" in page


def test_only_current_borrowing_statuses_are_displayed(app_factory):
    borrow_requests = [
        _approved_request(
            request_id="BR001",
            book_title="Approved Book",
            status="Approved",
        ),
        _approved_request(
            request_id="BR002",
            book_title="Issued Book",
            status="Issued",
        ),
        _approved_request(
            request_id="BR003",
            book_title="Pending Book",
            status="Pending",
        ),
        _approved_request(
            request_id="BR004",
            book_title="Returned Book",
            status="Returned",
        ),
        _approved_request(
            request_id="BR005",
            book_title="Rejected Book",
            status="Rejected",
        ),
    ]

    app = app_factory(borrow_requests=borrow_requests)
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Approved Book" in page
    assert "Issued Book" in page
    assert "Pending Book" not in page
    assert "Returned Book" not in page
    assert "Rejected Book" not in page


def test_remaining_borrowing_period_is_displayed(app_factory, monkeypatch):
    monkeypatch.setattr(
        catalogue_routes,
        "_today",
        lambda: date(2026, 7, 10),
    )
    borrow_requests = [
        _approved_request(
            borrow_date="2026-07-01",
            due_date="2026-07-15",
        )
    ]

    app = app_factory(borrow_requests=borrow_requests)
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2026-07-01" in page
    assert "2026-07-15" in page
    assert "5 days remaining" in page


def test_due_date_is_derived_from_scrum_16_request_data(
    app_factory,
    monkeypatch,
):
    """SCRUM-677 integrates with the request record created by SCRUM-16."""
    monkeypatch.setattr(
        catalogue_routes,
        "_today",
        lambda: date(2026, 7, 10),
    )
    borrow_requests = [
        _approved_request(
            request_date="2026-07-01 09:30:00",
            borrowing_period_days=14,
            due_date=None,
            borrow_date=None,
        )
    ]

    app = app_factory(borrow_requests=borrow_requests)
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2026-07-01" in page
    assert "2026-07-15" in page
    assert "14 days" in page
    assert "5 days remaining" in page


def test_due_today_message_is_displayed(app_factory, monkeypatch):
    monkeypatch.setattr(
        catalogue_routes,
        "_today",
        lambda: date(2026, 7, 15),
    )
    app = app_factory(
        borrow_requests=[
            _approved_request(due_date="2026-07-15")
        ]
    )
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Due today" in page
    assert "remaining-period-due-today" in page


def test_overdue_borrowing_period_is_displayed(app_factory, monkeypatch):
    monkeypatch.setattr(
        catalogue_routes,
        "_today",
        lambda: date(2026, 7, 18),
    )
    app = app_factory(
        borrow_requests=[
            _approved_request(due_date="2026-07-15")
        ]
    )
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Overdue by 3 days" in page
    assert "remaining-period-overdue" in page


def test_other_students_borrowed_books_are_not_displayed(app_factory):
    borrow_requests = [
        _approved_request(
            request_id="BR001",
            student_id="S001",
            book_title="Current Student Book",
        ),
        _approved_request(
            request_id="BR002",
            student_id="S999",
            book_title="Another Student Book",
        ),
    ]

    app = app_factory(borrow_requests=borrow_requests)
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current Student Book" in page
    assert "Another Student Book" not in page


def test_books_are_sorted_by_nearest_due_date(app_factory, monkeypatch):
    monkeypatch.setattr(
        catalogue_routes,
        "_today",
        lambda: date(2026, 7, 10),
    )
    borrow_requests = [
        _approved_request(
            request_id="BR001",
            book_title="Later Due Book",
            due_date="2026-07-25",
        ),
        _approved_request(
            request_id="BR002",
            book_title="Earlier Due Book",
            due_date="2026-07-12",
        ),
    ]

    app = app_factory(borrow_requests=borrow_requests)
    client = app.test_client()

    response = client.get("/catalogue/my-borrowed-books")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.index("Earlier Due Book") < page.index("Later Due Book")


def test_catalogue_contains_borrowed_books_navigation(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Borrowed Books" in page
    assert "/catalogue/my-borrowed-books" in page
