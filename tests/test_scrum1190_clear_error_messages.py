# SCRUM-1190: Display clear security, availability, and database errors

from modules.catalogue_reservation import routes as catalogue_routes


TECHNICAL_ERROR = (
    "Firestore permission denied: serviceAccountKey.json "
    "contains project_secret_123"
)


class FailOnceFirestore:
    """Raise one technical failure, then delegate later calls normally."""

    def __init__(self, delegate):
        self._delegate = delegate
        self._has_failed = False

    def collection(self, collection_name):
        if not self._has_failed:
            self._has_failed = True
            raise RuntimeError(TECHNICAL_ERROR)

        return self._delegate.collection(collection_name)


def _install_fail_once_database(app, monkeypatch):
    fake_db = app.extensions["fake_firestore"]
    monkeypatch.setattr(
        catalogue_routes,
        "db",
        FailOnceFirestore(fake_db),
    )


def _reservation():
    return {
        "reservation_id": "R001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Secure Software Design",
        "reservation_date": "2026-07-27 10:00:00",
        "status": "Active",
    }


def _unavailable_book():
    return {
        "book_id": "B001",
        "title": "Secure Software Design",
        "status": "Unavailable",
        "available_copies": 0,
    }


def test_catalogue_database_error_is_clear_and_hides_technical_details(
    app_factory,
    monkeypatch,
):
    app = app_factory()
    _install_fail_once_database(app, monkeypatch)
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert (
        "We could not load the catalogue right now. "
        "Please try again later."
    ) in page
    assert TECHNICAL_ERROR not in page
    assert "serviceAccountKey.json" not in page
    assert "project_secret_123" not in page


def test_reservation_database_error_is_clear_and_hides_details(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_unavailable_book()])
    _install_fail_once_database(app, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert (
        "We could not complete your reservation right now. "
        "Please try again later."
    ) in page
    assert TECHNICAL_ERROR not in page


def test_cancellation_database_error_is_clear_and_hides_details(
    app_factory,
    monkeypatch,
):
    app = app_factory(reservations=[_reservation()])
    _install_fail_once_database(app, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/catalogue/cancel-reservation/R001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert (
        "We could not cancel the reservation right now. "
        "Please try again later."
    ) in page
    assert TECHNICAL_ERROR not in page
    stored = app.extensions["fake_firestore"].collections["reservations"][0]
    assert stored["status"] == "Active"


def test_borrow_request_database_error_is_clear_and_hides_details(
    app_factory,
    monkeypatch,
):
    book = _unavailable_book()
    book.update(status="Available", available_copies=1)
    app = app_factory(books=[book])
    _install_fail_once_database(app, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert (
        "We could not submit your borrowing request right now. "
        "Please try again later."
    ) in page
    assert TECHNICAL_ERROR not in page
    requests = app.extensions["fake_firestore"].collections[
        "borrow_requests"
    ]
    assert requests == []


def test_unavailable_book_message_gives_student_a_next_action(app_factory):
    app = app_factory(books=[_unavailable_book()])
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "This book is unavailable" in page
    assert "Please reserve it instead" in page


def test_duplicate_reservation_message_explains_the_problem(app_factory):
    app = app_factory(
        books=[_unavailable_book()],
        reservations=[_reservation()],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert (
        "You already have an active reservation for this book."
    ) in page
