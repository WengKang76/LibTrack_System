import pytest

import modules.book_catalogue.routes as book_routes

pytestmark = pytest.mark.usefixtures("login_as_librarian")


BOOK_ID = "BOOK001"
COPY_ID = "COPY-BOOK001-001"


# ============================================================
# FAKE FIRESTORE
# ============================================================


class FakeCopyReference:
    def __init__(
        self,
        database,
        copy_id,
    ):
        self.database = database
        self.copy_id = copy_id

    def delete(self):
        self.database.deleted_copy_ids.append(self.copy_id)


class FakeCopyDocument:
    def __init__(
        self,
        database,
        copy_id,
    ):
        self.id = copy_id

        self.reference = FakeCopyReference(
            database,
            copy_id,
        )


class FakeCopiesCollection:
    def __init__(
        self,
        database,
    ):
        self.database = database

    def document(self, copy_id):
        return FakeCopyReference(
            self.database,
            copy_id,
        )

    def stream(self):
        return [
            FakeCopyDocument(
                self.database,
                COPY_ID,
            )
        ]


class FakeBookReference:
    def __init__(
        self,
        database,
        book_id,
    ):
        self.database = database
        self.book_id = book_id

    def collection(self, collection_name):
        assert collection_name == "copies"

        return FakeCopiesCollection(self.database)

    def delete(self):
        self.database.deleted_book_ids.append(self.book_id)


class FakeBooksCollection:
    def __init__(self, database):
        self.database = database

    def document(self, book_id):
        return FakeBookReference(
            self.database,
            book_id,
        )


class FakeDatabase:
    def __init__(self):
        self.deleted_book_ids = []
        self.deleted_copy_ids = []

    def collection(self, collection_name):
        assert collection_name == book_routes.COLLECTION_BOOKS

        return FakeBooksCollection(self)


# ============================================================
# FIXTURE
# ============================================================


@pytest.fixture
def deletion_environment(
    monkeypatch,
):
    fake_database = FakeDatabase()

    copy_record = {
        "document_id": COPY_ID,
        "copy_id": COPY_ID,
        "book_id": BOOK_ID,
        "copy_number": 1,
        "status": "Available",
        "condition": "Good",
    }

    copies = [copy_record]

    sync_calls = []

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    monkeypatch.setattr(
        book_routes,
        "get_book_by_id",
        lambda book_id: {
            "book_id": book_id,
            "title": "Test Book",
        },
    )

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: copies,
    )

    monkeypatch.setattr(
        book_routes,
        "_get_book_copy_by_id",
        lambda book_id, copy_id: (copy_record),
    )

    monkeypatch.setattr(
        book_routes,
        "_sync_book_inventory_from_copies",
        lambda book_id: sync_calls.append(book_id),
    )

    return {
        "database": fake_database,
        "copy_record": copy_record,
        "copies": copies,
        "sync_calls": sync_calls,
    }


# ============================================================
# HELPER VALIDATION
# ============================================================


@pytest.mark.parametrize(
    "status",
    [
        "Borrowed",
        "borrowed",
        " BORROWED ",
        "Reserved",
        "reserved",
    ],
)
def test_scrum_1182_detects_active_transaction(
    status,
):
    copy_record = {
        "status": status,
    }

    assert book_routes._copy_has_active_transaction(copy_record) is True


@pytest.mark.parametrize(
    "status",
    [
        "Available",
        "Damaged",
        "Lost",
        "",
    ],
)
def test_scrum_1182_allows_safe_status(
    status,
):
    copy_record = {
        "status": status,
    }

    assert book_routes._copy_has_active_transaction(copy_record) is False


# ============================================================
# COMPLETE BOOK DELETION
# ============================================================


def test_scrum_1182_prevents_borrowed_book_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Borrowed"

    response = client.post(f"/books/delete/{BOOK_ID}")

    assert response.status_code == 400

    database = deletion_environment["database"]

    assert database.deleted_book_ids == []
    assert database.deleted_copy_ids == []

    assert b"cannot be deleted" in response.data


def test_scrum_1182_prevents_reserved_book_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Reserved"

    response = client.post(f"/books/delete/{BOOK_ID}")

    assert response.status_code == 400

    database = deletion_environment["database"]

    assert database.deleted_book_ids == []
    assert database.deleted_copy_ids == []


def test_scrum_1182_allows_safe_book_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Available"

    response = client.post(f"/books/delete/{BOOK_ID}")

    assert response.status_code == 302

    database = deletion_environment["database"]

    assert database.deleted_book_ids == [BOOK_ID]

    assert database.deleted_copy_ids == [COPY_ID]


# ============================================================
# PHYSICAL COPY DELETION
# ============================================================


def test_scrum_1182_prevents_borrowed_copy_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Borrowed"

    response = client.post((f"/books/copies/delete/" f"{BOOK_ID}/{COPY_ID}"))

    assert response.status_code == 400

    assert deletion_environment["database"].deleted_copy_ids == []

    assert deletion_environment["sync_calls"] == []


def test_scrum_1182_prevents_reserved_copy_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Reserved"

    response = client.post((f"/books/copies/delete/" f"{BOOK_ID}/{COPY_ID}"))

    assert response.status_code == 400

    assert deletion_environment["database"].deleted_copy_ids == []

    assert deletion_environment["sync_calls"] == []


def test_scrum_1182_allows_available_copy_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Available"

    response = client.post((f"/books/copies/delete/" f"{BOOK_ID}/{COPY_ID}"))

    assert response.status_code == 302

    assert deletion_environment["database"].deleted_copy_ids == [COPY_ID]

    assert deletion_environment["sync_calls"] == [BOOK_ID]


def test_scrum_1182_allows_damaged_copy_deletion(
    client,
    deletion_environment,
):
    deletion_environment["copy_record"]["status"] = "Damaged"

    response = client.post((f"/books/copies/delete/" f"{BOOK_ID}/{COPY_ID}"))

    assert response.status_code == 302

    assert deletion_environment["database"].deleted_copy_ids == [COPY_ID]

    assert deletion_environment["sync_calls"] == [BOOK_ID]
