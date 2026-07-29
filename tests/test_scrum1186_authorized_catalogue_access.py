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


def test_unauthenticated_user_is_redirected_to_login(app_factory):
    app = app_factory(authenticated=False)
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    messages = _get_flashed_messages(client)
    assert any("Please log in" in message for message in messages)


def test_librarian_cannot_access_student_catalogue(app_factory):
    app = app_factory(
        authenticated=True,
        session_user_id="LIB001",
        session_role="librarian",
    )
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")

    messages = _get_flashed_messages(client)
    assert any("Access denied" in message for message in messages)


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
