import pytest

import modules.book_catalogue.routes as book_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


BOOK = {
    "book_id": "BOOK001",
    "title": "Clean Code",
    "author": "Robert C. Martin",
}


COPY = {
    "document_id": "COPY-BOOK001-001",
    "copy_id": "COPY-BOOK001-001",
    "book_id": "BOOK001",
    "copy_number": 1,
    "status": "Available",
    "condition": "Good",
}


class FakeCopyDocument:
    def __init__(self):
        self.updated_data = None

    def update(self, data):
        self.updated_data = dict(data)


class FakeCopiesCollection:
    def __init__(self, copy_document):
        self.copy_document = copy_document

    def document(self, copy_id):
        return self.copy_document


class FakeBookDocument:
    def __init__(self, copy_document):
        self.copy_document = copy_document

    def collection(self, name):
        return FakeCopiesCollection(
            self.copy_document
        )


class FakeBooksCollection:
    def __init__(self, copy_document):
        self.copy_document = copy_document

    def document(self, book_id):
        return FakeBookDocument(
            self.copy_document
        )


class FakeDatabase:
    def __init__(self):
        self.copy_document = (
            FakeCopyDocument()
        )

    def collection(self, name):
        return FakeBooksCollection(
            self.copy_document
        )


@pytest.fixture
def status_environment(
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    monkeypatch.setattr(
        book_routes,
        "get_book_by_id",
        lambda book_id: dict(BOOK),
    )

    monkeypatch.setattr(
        book_routes,
        "_get_book_copy_by_id",
        lambda book_id, copy_id: (
            dict(COPY)
        ),
    )

    monkeypatch.setattr(
        book_routes,
        "_sync_book_inventory_from_copies",
        lambda book_id: None,
    )

    return fake_database


def _status_url():
    return (
        "/books/copies/status/"
        "BOOK001/"
        "COPY-BOOK001-001"
    )


def test_scrum_1530_damaged_requires_reason(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Damaged",
            "reason": "",
            "confirm_status_change": (
                "confirmed"
            ),
        },
    )

    assert response.status_code == 400

    assert (
        b"Please provide a reason"
        in response.data
    )

    assert (
        status_environment
        .copy_document
        .updated_data
        is None
    )


def test_scrum_1530_lost_requires_reason(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Lost",
            "reason": "",
            "confirm_status_change": (
                "confirmed"
            ),
        },
    )

    assert response.status_code == 400

    assert (
        b"Please provide a reason"
        in response.data
    )


def test_scrum_1530_damaged_requires_confirmation(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Damaged",
            "reason": (
                "Cover and several pages "
                "are badly damaged."
            ),
        },
    )

    assert response.status_code == 400

    assert (
        b"Please confirm"
        in response.data
    )


def test_scrum_1530_lost_requires_confirmation(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Lost",
            "reason": (
                "The copy could not be "
                "located after checking."
            ),
        },
    )

    assert response.status_code == 400

    assert (
        b"Please confirm"
        in response.data
    )


def test_scrum_1530_damaged_reason_is_stored(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Damaged",
            "reason": (
                "Water damage found "
                "during inspection."
            ),
            "confirm_status_change": (
                "confirmed"
            ),
        },
    )

    assert response.status_code == 302

    updated_data = (
        status_environment
        .copy_document
        .updated_data
    )

    assert (
        updated_data["status"]
        == "Damaged"
    )

    assert (
        updated_data["condition"]
        == "Damaged"
    )

    assert (
        updated_data["status_reason"]
        == (
            "Water damage found "
            "during inspection."
        )
    )

    assert (
        updated_data["status_reason_type"]
        == "Damage"
    )


def test_scrum_1530_lost_reason_is_stored(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Lost",
            "reason": (
                "Copy was reported "
                "missing."
            ),
            "confirm_status_change": (
                "confirmed"
            ),
        },
    )

    assert response.status_code == 302

    updated_data = (
        status_environment
        .copy_document
        .updated_data
    )

    assert updated_data["status"] == "Lost"

    assert (
        updated_data["condition"]
        == "Lost"
    )

    assert (
        updated_data["status_reason"]
        == "Copy was reported missing."
    )

    assert (
        updated_data["status_reason_type"]
        == "Loss"
    )


def test_scrum_1530_normal_status_does_not_require_reason(
    client,
    status_environment,
):
    response = client.post(
        _status_url(),
        data={
            "status": "Available",
        },
    )

    assert response.status_code == 302

    updated_data = (
        status_environment
        .copy_document
        .updated_data
    )

    assert (
        updated_data["status"]
        == "Available"
    )

    assert (
        updated_data["condition"]
        == "Good"
    )

    assert (
        updated_data["status_reason"]
        == ""
    )

    assert (
        updated_data["status_reason_type"]
        == ""
    )