# SCRUM-1192: Hide inactive, deactivated, and unlisted books


def _book(book_id="B001", title="Visible Book", **changes):
    book = {
        "book_id": book_id,
        "title": title,
        "author": "Test Author",
        "category": "Computing",
        "status": "Available",
        "available_copies": 2,
        "total_copies": 2,
        "catalogue_status": "Active",
        "is_visible_to_students": True,
    }
    book.update(changes)
    return book


def test_inactive_book_is_hidden_from_student_catalogue(app_factory):
    app = app_factory(
        books=[
            _book(),
            _book(
                "B002",
                "Inactive Book",
                catalogue_status="Inactive",
                is_visible_to_students=False,
            ),
        ]
    )
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Visible Book" in page
    assert "Inactive Book" not in page


def test_unlisted_book_is_hidden_from_available_books(app_factory):
    app = app_factory(
        books=[
            _book(
                "B002",
                "Unlisted Book",
                catalogue_status="Unlisted",
                is_visible_to_students=False,
            )
        ]
    )
    client = app.test_client()

    response = client.get("/catalogue/available")

    assert response.status_code == 200
    assert "Unlisted Book" not in response.get_data(as_text=True)


def test_hidden_book_direct_details_url_is_blocked(app_factory):
    app = app_factory(
        books=[
            _book(
                catalogue_status="Inactive",
                is_visible_to_students=False,
            )
        ]
    )
    client = app.test_client()

    response = client.get(
        "/catalogue/details/B001",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Book not found" in response.get_data(as_text=True)


def test_hidden_book_cannot_be_reserved_through_direct_url(app_factory):
    app = app_factory(
        books=[
            _book(
                status="Unavailable",
                available_copies=0,
                catalogue_status="Deactivated",
                is_visible_to_students=False,
            )
        ]
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
    assert "Book not found" in response.get_data(as_text=True)
    assert reservations == []


def test_hidden_book_cannot_be_borrowed_through_direct_url(app_factory):
    app = app_factory(
        books=[
            _book(
                catalogue_status="Inactive",
                is_visible_to_students=False,
            )
        ]
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
    assert "Book not found" in response.get_data(as_text=True)
    assert requests == []


def test_legacy_book_without_visibility_fields_remains_visible(app_factory):
    legacy_book = _book()
    legacy_book.pop("catalogue_status")
    legacy_book.pop("is_visible_to_students")

    app = app_factory(books=[legacy_book])
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 200
    assert "Visible Book" in response.get_data(as_text=True)
