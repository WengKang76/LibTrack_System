import pytest

import modules.book_catalogue.routes as book_routes

# ============================================================
# FAKE FIRESTORE
# ============================================================


class FakeBookDocumentReference:
    def __init__(self):
        self.book_id = None

        # Simulate incorrect old totals.
        self.data = {
            "total_copies": 99,
            "available_copies": 99,
            "status": "Available",
        }

        self.update_history = []

    def update(self, updated_data):
        updated_data = dict(updated_data)

        self.data.update(updated_data)
        self.update_history.append(updated_data)


class FakeBooksCollection:
    def __init__(self, book_reference):
        self.book_reference = book_reference

    def document(self, book_id):
        self.book_reference.book_id = book_id
        return self.book_reference


class FakeDatabase:
    def __init__(self):
        self.book_reference = FakeBookDocumentReference()

    def collection(self, collection_name):
        assert collection_name == book_routes.COLLECTION_BOOKS

        return FakeBooksCollection(self.book_reference)


# ============================================================
# FIXTURE
# ============================================================


@pytest.fixture
def inventory_environment(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    return fake_database


# ============================================================
# SCRUM-1183: COPY-SUMMARY CALCULATION
# ============================================================


def test_scrum_1183_calculates_copy_summary():
    copies = [
        {"status": "Available"},
        {"status": "Available"},
        {"status": "Borrowed"},
        {"status": "Reserved"},
        {"status": "Damaged"},
        {"status": "Lost"},
    ]

    summary = book_routes._calculate_copy_summary(copies)

    assert summary == {
        "total": 6,
        "available": 2,
        "borrowed": 1,
        "reserved": 1,
        "damaged": 1,
        "lost": 1,
    }


def test_scrum_1183_status_is_case_insensitive():
    copies = [
        {"status": "available"},
        {"status": "AVAILABLE"},
        {"status": " Borrowed "},
        {"status": "damaged"},
    ]

    summary = book_routes._calculate_copy_summary(copies)

    assert summary["total"] == 4
    assert summary["available"] == 2
    assert summary["borrowed"] == 1
    assert summary["damaged"] == 1


# ============================================================
# SCRUM-1183: PARENT-BOOK TOTAL RECALCULATION
# ============================================================


def test_scrum_1183_recalculates_parent_totals(
    inventory_environment,
    monkeypatch,
):
    copies = [
        {"status": "Available"},
        {"status": "Available"},
        {"status": "Borrowed"},
        {"status": "Reserved"},
        {"status": "Damaged"},
        {"status": "Lost"},
    ]

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: copies,
    )

    result = book_routes._sync_book_inventory_from_copies("BOOK001")

    saved_book = inventory_environment.book_reference.data

    assert saved_book["total_copies"] == 6
    assert saved_book["available_copies"] == 2
    assert saved_book["status"] == "Available"

    assert result["total"] == 6
    assert result["available"] == 2


def test_scrum_1183_corrects_inaccurate_old_totals(
    inventory_environment,
    monkeypatch,
):
    copies = [
        {"status": "Available"},
        {"status": "Borrowed"},
        {"status": "Borrowed"},
    ]

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: copies,
    )

    book_routes._sync_book_inventory_from_copies("BOOK001")

    saved_book = inventory_environment.book_reference.data

    # Old values were both 99.
    assert saved_book["total_copies"] == 3
    assert saved_book["available_copies"] == 1
    assert saved_book["status"] == "Available"


def test_scrum_1183_marks_book_unavailable_when_zero_available(
    inventory_environment,
    monkeypatch,
):
    copies = [
        {"status": "Borrowed"},
        {"status": "Reserved"},
        {"status": "Damaged"},
        {"status": "Lost"},
    ]

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: copies,
    )

    book_routes._sync_book_inventory_from_copies("BOOK001")

    saved_book = inventory_environment.book_reference.data

    assert saved_book["total_copies"] == 4
    assert saved_book["available_copies"] == 0
    assert saved_book["status"] == "Unavailable"


def test_scrum_1183_handles_book_with_no_copies(
    inventory_environment,
    monkeypatch,
):
    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: [],
    )

    result = book_routes._sync_book_inventory_from_copies("BOOK001")

    saved_book = inventory_environment.book_reference.data

    assert saved_book["total_copies"] == 0
    assert saved_book["available_copies"] == 0
    assert saved_book["status"] == "Unavailable"

    assert result["total"] == 0
    assert result["available"] == 0


def test_scrum_1183_updates_correct_book_document(
    inventory_environment,
    monkeypatch,
):
    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: [
            {"status": "Available"},
        ],
    )

    book_routes._sync_book_inventory_from_copies("BOOK888")

    assert inventory_environment.book_reference.book_id == "BOOK888"


def test_scrum_1183_stores_updated_timestamp(
    inventory_environment,
    monkeypatch,
):
    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: [
            {"status": "Available"},
        ],
    )

    book_routes._sync_book_inventory_from_copies("BOOK001")

    saved_book = inventory_environment.book_reference.data

    assert "updated_at" in saved_book
    assert isinstance(
        saved_book["updated_at"],
        str,
    )
    assert saved_book["updated_at"]
