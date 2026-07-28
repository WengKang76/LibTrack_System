import pytest

import modules.book_catalogue.routes as book_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


BOOK_ID = "BOOK001"
COPY_ID = "COPY-BOOK001-001"


# ============================================================
# FAKE FIRESTORE
# ============================================================

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

    def update(self, updated_data):
        self.database.copy_updates.append(
            {
                "book_id": self.book_id,
                "copy_id": self.copy_id,
                "updated_data": dict(
                    updated_data
                ),
            }
        )


class FakeCopiesCollection:
    def __init__(
        self,
        database,
        book_id,
    ):
        self.database = database
        self.book_id = book_id

    def document(self, copy_id):
        return FakeCopyDocumentReference(
            self.database,
            self.book_id,
            copy_id,
        )


class FakeBookDocumentReference:
    def __init__(
        self,
        database,
        book_id,
    ):
        self.database = database
        self.book_id = book_id

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


class FakeDatabase:
    def __init__(self):
        self.copy_updates = []

    def collection(self, collection_name):
        assert (
            collection_name
            == book_routes.COLLECTION_BOOKS
        )

        return FakeBooksCollection(self)


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture
def availability_environment(
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
        "_get_book_copy_by_id",
        lambda book_id, copy_id: (
            copy_record
        ),
    )

    def fake_sync_inventory(book_id):
        sync_calls.append(book_id)

        return {
            "total": 1,
            "available": 0,
            "borrowed": 0,
            "reserved": 0,
            "damaged": 0,
            "lost": 0,
        }

    monkeypatch.setattr(
        book_routes,
        "_sync_book_inventory_from_copies",
        fake_sync_inventory,
    )

    return {
        "database": fake_database,
        "copy_record": copy_record,
        "sync_calls": sync_calls,
    }


# ============================================================
# SCRUM-1185: STATUS CHANGES
# ============================================================

@pytest.mark.parametrize(
    (
        "selected_status",
        "expected_condition",
    ),
    [
        ("Available", "Good"),
        ("Borrowed", "Good"),
        ("Reserved", "Good"),
        ("Damaged", "Damaged"),
        ("Lost", "Lost"),
    ],
)
def test_scrum_1185_status_change_updates_copy(
    client,
    availability_environment,
    selected_status,
    expected_condition,
):
    response = client.post(
        (
            f"/books/copies/status/"
            f"{BOOK_ID}/{COPY_ID}"
        ),
        data={
            "status": selected_status,
        },
    )

    assert response.status_code == 302

    database = availability_environment[
        "database"
    ]

    assert len(database.copy_updates) == 1

    update_record = database.copy_updates[0]

    assert update_record["book_id"] == BOOK_ID
    assert update_record["copy_id"] == COPY_ID

    updated_data = update_record[
        "updated_data"
    ]

    assert (
        updated_data["status"]
        == selected_status
    )

    assert (
        updated_data["condition"]
        == expected_condition
    )

    assert "updated_at" in updated_data


# ============================================================
# SCRUM-1185: AUTOMATIC INVENTORY SYNCHRONISATION
# ============================================================

@pytest.mark.parametrize(
    "selected_status",
    [
        "Available",
        "Borrowed",
        "Reserved",
        "Damaged",
        "Lost",
    ],
)
def test_scrum_1185_status_change_recalculates_book(
    client,
    availability_environment,
    selected_status,
):
    response = client.post(
        (
            f"/books/copies/status/"
            f"{BOOK_ID}/{COPY_ID}"
        ),
        data={
            "status": selected_status,
        },
    )

    assert response.status_code == 302

    assert availability_environment[
        "sync_calls"
    ] == [BOOK_ID]


def test_scrum_1185_invalid_status_does_not_sync(
    client,
    availability_environment,
):
    response = client.post(
        (
            f"/books/copies/status/"
            f"{BOOK_ID}/{COPY_ID}"
        ),
        data={
            "status": "Invalid Status",
        },
    )

    assert response.status_code == 400

    assert availability_environment[
        "database"
    ].copy_updates == []

    assert availability_environment[
        "sync_calls"
    ] == []


# ============================================================
# SCRUM-1185: RESTORE DAMAGED COPY
# ============================================================

def test_scrum_1185_restore_changes_copy_to_available(
    client,
    availability_environment,
):
    availability_environment[
        "copy_record"
    ]["status"] = "Damaged"

    availability_environment[
        "copy_record"
    ]["condition"] = "Damaged"

    response = client.post(
        (
            f"/books/copies/restore/"
            f"{BOOK_ID}/{COPY_ID}"
        )
    )

    assert response.status_code == 302

    database = availability_environment[
        "database"
    ]

    assert len(database.copy_updates) == 1

    updated_data = database.copy_updates[
        0
    ]["updated_data"]

    assert (
        updated_data["status"]
        == "Available"
    )

    assert (
        updated_data["condition"]
        == "Good"
    )

    assert "restored_at" in updated_data
    assert "updated_at" in updated_data


def test_scrum_1185_restore_recalculates_book(
    client,
    availability_environment,
):
    availability_environment[
        "copy_record"
    ]["status"] = "Damaged"

    response = client.post(
        (
            f"/books/copies/restore/"
            f"{BOOK_ID}/{COPY_ID}"
        )
    )

    assert response.status_code == 302

    assert availability_environment[
        "sync_calls"
    ] == [BOOK_ID]


def test_scrum_1185_cannot_restore_non_damaged_copy(
    client,
    availability_environment,
):
    availability_environment[
        "copy_record"
    ]["status"] = "Borrowed"

    response = client.post(
        (
            f"/books/copies/restore/"
            f"{BOOK_ID}/{COPY_ID}"
        )
    )

    assert response.status_code == 400

    assert availability_environment[
        "database"
    ].copy_updates == []

    assert availability_environment[
        "sync_calls"
    ] == []