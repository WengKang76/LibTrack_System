from datetime import datetime

import pytest

import modules.book_catalogue.routes as book_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None

        return dict(self._data)


class FakeCopyDocumentReference:
    def __init__(
        self,
        database,
        book_id,
        copy_id,
    ):
        self.database = database
        self.book_id = book_id
        self.copy_id = copy_id
        self.id = copy_id

    def get(self):
        copy_data = (
            self.database
            .copies
            .get(self.book_id, {})
            .get(self.copy_id)
        )

        return FakeDocumentSnapshot(
            self.copy_id,
            copy_data,
        )

    def update(self, updated_data):
        if self.copy_id not in self.database.copies.get(
            self.book_id,
            {},
        ):
            raise KeyError(
                f"Unknown copy ID: {self.copy_id}"
            )

        self.database.copies[self.book_id][
            self.copy_id
        ].update(dict(updated_data))

        self.database.copy_update_history.append(
            {
                "book_id": self.book_id,
                "copy_id": self.copy_id,
                "updated_data": dict(updated_data),
            }
        )


class FakeCopiesCollection:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id

    def document(self, copy_id):
        return FakeCopyDocumentReference(
            self.database,
            self.book_id,
            copy_id,
        )

    def stream(self):
        copy_records = self.database.copies.get(
            self.book_id,
            {},
        )

        return [
            FakeDocumentSnapshot(copy_id, data)
            for copy_id, data in copy_records.items()
        ]


class FakeBookDocumentReference:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id
        self.id = book_id

    def get(self):
        book_data = self.database.books.get(
            self.book_id
        )

        return FakeDocumentSnapshot(
            self.book_id,
            book_data,
        )

    def collection(self, collection_name):
        assert collection_name == "copies"

        return FakeCopiesCollection(
            self.database,
            self.book_id,
        )


class FakeBooksCollection:
    def __init__(self, database):
        self.database = database

    def document(self, book_id):
        return FakeBookDocumentReference(
            self.database,
            book_id,
        )

    def stream(self):
        return [
            FakeDocumentSnapshot(book_id, data)
            for book_id, data
            in self.database.books.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.books = {
            "BOOK001": {
                "title": "Python Programming",
                "author": "Sherman",
                "isbn": "9780000000001",
                "category": "Programming",
                "publisher": "Technology Press",
                "publication_year": "2024",
                "description": (
                    "A beginner-friendly programming book."
                ),
                "total_copies": 2,
                "available_copies": 1,
                "status": "Available",
            }
        }

        self.copies = {
            "BOOK001": {
                "COPY-BOOK001-001": {
                    "copy_id": "COPY-BOOK001-001",
                    "book_id": "BOOK001",
                    "copy_number": 1,
                    "status": "Available",
                    "condition": "Good",
                    "created_at": "2026-07-15 09:00:00",
                },
                "COPY-BOOK001-002": {
                    "copy_id": "COPY-BOOK001-002",
                    "book_id": "BOOK001",
                    "copy_number": 2,
                    "status": "Borrowed",
                    "condition": "Good",
                    "created_at": "2026-07-15 09:01:00",
                },
            }
        }

        self.copy_update_history = []

    def collection(self, collection_name):
        assert collection_name == "books"

        return FakeBooksCollection(self)


def use_fake_database(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    return fake_database


# ============================================================
# SCRUM-695: UPDATE INDIVIDUAL PHYSICAL COPY STATUS
# ============================================================


def test_scrum_695_update_status_page_loads(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        )
    )

    assert response.status_code == 200
    assert b"Update Physical Copy Status" in response.data
    assert b"Python Programming" in response.data
    assert b"COPY-BOOK001-001" in response.data
    assert b"Available" in response.data


def test_scrum_695_page_displays_all_status_options(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        )
    )

    assert response.status_code == 200

    expected_statuses = [
        b"Available",
        b"Borrowed",
        b"Reserved",
        b"Lost",
        b"Damaged",
    ]

    for status in expected_statuses:
        assert status in response.data


@pytest.mark.parametrize(
    "new_status",
    [
        "Available",
        "Borrowed",
        "Reserved",
        "Lost",
        "Damaged",
    ],
)
def test_scrum_695_accepts_each_valid_status(
    client,
    monkeypatch,
    new_status,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": new_status},
    )

    assert response.status_code == 302

    updated_copy = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-001"]

    assert updated_copy["status"] == new_status
    assert "updated_at" in updated_copy

    datetime.strptime(
        updated_copy["updated_at"],
        "%Y-%m-%d %H:%M:%S",
    )


def test_scrum_695_updates_only_selected_copy(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    second_copy_before = dict(
        fake_database.copies[
            "BOOK001"
        ]["COPY-BOOK001-002"]
    )

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Damaged"},
    )

    assert response.status_code == 302

    first_copy = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-001"]

    second_copy = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-002"]

    assert first_copy["status"] == "Damaged"
    assert second_copy == second_copy_before


def test_scrum_695_records_one_update_operation(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Reserved"},
    )

    assert len(
        fake_database.copy_update_history
    ) == 1

    update_record = (
        fake_database.copy_update_history[0]
    )

    assert update_record["book_id"] == "BOOK001"

    assert update_record["copy_id"] == (
        "COPY-BOOK001-001"
    )

    assert (
        update_record["updated_data"]["status"]
        == "Reserved"
    )


def test_scrum_695_redirects_to_book_details(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Lost"},
    )

    assert response.status_code == 302

    assert response.headers["Location"].endswith(
        "/books/details/BOOK001"
    )


def test_scrum_695_displays_success_message(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Damaged"},
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        b"COPY-BOOK001-001 status was updated "
        b"to Damaged successfully."
        in response.data
    )


def test_scrum_695_rejects_invalid_status(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    original_status = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-001"]["status"]

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Destroyed"},
    )

    assert response.status_code == 400

    assert (
        b"Please select a valid copy status."
        in response.data
    )

    current_status = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-001"]["status"]

    assert current_status == original_status

    assert (
        fake_database.copy_update_history
        == []
    )


def test_scrum_695_rejects_missing_status(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={},
    )

    assert response.status_code == 400

    assert (
        b"Please select a valid copy status."
        in response.data
    )

    assert (
        fake_database.copies[
            "BOOK001"
        ]["COPY-BOOK001-001"]["status"]
        == "Available"
    )


def test_scrum_695_unknown_book_returns_404(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get(
        (
            "/books/copies/status/"
            "UNKNOWN/COPY-BOOK001-001"
        )
    )

    assert response.status_code == 404
    assert b"Book record not found." in response.data


def test_scrum_695_unknown_copy_returns_404(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get(
        (
            "/books/copies/status/"
            "BOOK001/UNKNOWN-COPY"
        )
    )

    assert response.status_code == 404

    assert (
        b"Physical book copy not found."
        in response.data
    )


def test_scrum_695_summary_changes_after_status_update(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    update_response = client.post(
        (
            "/books/copies/status/"
            "BOOK001/COPY-BOOK001-001"
        ),
        data={"status": "Damaged"},
    )

    assert update_response.status_code == 302

    details_response = client.get(
        "/books/details/BOOK001"
    )

    assert details_response.status_code == 200

    assert b"Damaged" in details_response.data
    assert b"COPY-BOOK001-001" in details_response.data