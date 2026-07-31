# SCRUM-1186: Validate authenticated student access


def _get_flashed_messages(client):
    """Return messages currently stored in the Flask test session."""
    with client.session_transaction() as session_data:
        return [
            message
            for _category, message
            in session_data.get("_flashes", [])
        ]


def test_authenticated_student_can_access_catalogue(app_factory):
    app = app_factory(
        authenticated=True,
        session_user_id="S001",
        session_role="Student",
    )
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 200
    assert "Book Catalogue" in response.get_data(as_text=True)


def test_guest_user_can_preview_catalogue_without_login(app_factory):
    app = app_factory(
        books=[
            {
                "book_id": "B001",
                "title": "Preview Book",
                "status": "Available",
                "available_copies": 2,
            }
        ],
        authenticated=False,
    )
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 200
    assert "Preview Book" in response.get_data(as_text=True)


def test_unauthenticated_user_is_redirected_to_login_for_student_only_pages(app_factory):
    app = app_factory(authenticated=False)
    client = app.test_client()

    response = client.get("/catalogue/my-reservations")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")

    messages = _get_flashed_messages(client)
    assert any(
        "Please log in as a student to view your reservations." in message
        for message in messages
    )


def test_unauthenticated_user_is_redirected_for_reservations_and_borrowed_books(
    app_factory,
):
    app = app_factory(authenticated=False)
    client = app.test_client()

    reservations_response = client.get("/catalogue/my-reservations")
    borrowed_response = client.get("/catalogue/my-borrowed-books")

    assert reservations_response.status_code == 302
    assert borrowed_response.status_code == 302
    assert reservations_response.headers["Location"].endswith("/auth/login")
    assert borrowed_response.headers["Location"].endswith("/auth/login")

    messages = _get_flashed_messages(client)
    assert any(
        "Please log in as a student to view your reservations." in message
        for message in messages
    )
    assert any(
        "Please log in as a student to view your borrowed books." in message
        for message in messages
    )


def test_librarian_can_preview_catalogue(app_factory):
    app = app_factory(
        authenticated=True,
        session_user_id="LIB001",
        session_role="librarian",
    )
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 200
    assert "Book Catalogue" in response.get_data(as_text=True)


def test_unauthorized_reservation_and_borrow_actions_redirect_to_login(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Unavailable Book",
            "status": "Unavailable",
            "available_copies": 0,
        }
    ]
    app = app_factory(books=books, authenticated=False)
    client = app.test_client()

    reserve_response = client.get("/catalogue/reserve/B001")
    borrow_response = client.get("/catalogue/borrow/B001")

    assert reserve_response.status_code == 302
    assert borrow_response.status_code == 302
    assert reserve_response.headers["Location"].endswith("/auth/login")
    assert borrow_response.headers["Location"].endswith("/auth/login")

    messages = _get_flashed_messages(client)
    assert any(
        "Please log in as a student to reserve this book." in message
        for message in messages
    )
    assert any(
        "Please log in as a student to borrow this book." in message
        for message in messages
    )


def test_unauthorized_reservation_post_creates_no_record(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Unavailable Book",
            "status": "Unavailable",
            "available_copies": 0,
        }
    ]
    app = app_factory(books=books, authenticated=False)
    client = app.test_client()

    response = client.post("/catalogue/reserve/B001")
    reservations = app.extensions["fake_firestore"].collections[
        "reservations"
    ]

    assert response.status_code == 302
    assert reservations == []
