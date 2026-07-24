import copy
import re
from datetime import datetime

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

    def set(self, data):
        self.database.copies.setdefault(
            self.book_id,
            {},
        )

        self.database.copies[self.book_id][self.copy_id] = dict(data)


class FakeCopiesCollection:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id

    def stream(self):
        copy_records = self.database.copies.get(
            self.book_id,
            {},
        )

        return [
            FakeDocumentSnapshot(copy_id, data)
            for copy_id, data in copy_records.items()
        ]

    def document(self, copy_id):
        return FakeCopyDocumentReference(
            self.database,
            self.book_id,
            copy_id,
        )


class FakeBookDocumentReference:
    def __init__(self, database, book_id):
        self.database = database
        self.id = book_id
        self.book_id = book_id

    def get(self):
        book_data = self.database.books.get(self.book_id)

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

    def update(self, updated_data):
        if self.book_id not in self.database.books:
            raise KeyError(f"Unknown book ID: {self.book_id}")

        self.database.books[self.book_id].update(dict(updated_data))

        self.database.update_history.append(
            {
                "book_id": self.book_id,
                "updated_data": dict(updated_data),
            }
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
            for book_id, data in self.database.books.items()
        ]


class FakeDatabase:
    def __init__(self, include_copies=True):
        self.books = {
            "BOOK001": {
                "title": "Python Programming",
                "author": "Sherman",
                "isbn": "9780000000001",
                "category": "Programming",
                "publisher": "Technology Press",
                "publication_year": "2024",
                "description": ("A beginner-friendly programming book."),
                "total_copies": 5,
                "available_copies": 1,
                "status": "Available",
            }
        }

        self.copies = {"BOOK001": {}}

        if include_copies:
            self.copies["BOOK001"] = {
                "COPY-BOOK001-001": {
                    "copy_id": "COPY-BOOK001-001",
                    "book_id": "BOOK001",
                    "copy_number": 1,
                    "status": "Available",
                    "condition": "Good",
                    "created_at": "2026-07-10 10:00:00",
                },
                "COPY-BOOK001-002": {
                    "copy_id": "COPY-BOOK001-002",
                    "book_id": "BOOK001",
                    "copy_number": 2,
                    "status": "Borrowed",
                    "condition": "Good",
                    "created_at": "2026-07-10 10:01:00",
                },
                "COPY-BOOK001-003": {
                    "copy_id": "COPY-BOOK001-003",
                    "book_id": "BOOK001",
                    "copy_number": 3,
                    "status": "Reserved",
                    "condition": "Good",
                    "created_at": "2026-07-10 10:02:00",
                },
                "COPY-BOOK001-004": {
                    "copy_id": "COPY-BOOK001-004",
                    "book_id": "BOOK001",
                    "copy_number": 4,
                    "status": "Damaged",
                    "condition": "Damaged",
                    "created_at": "2026-07-10 10:03:00",
                },
                "COPY-BOOK001-005": {
                    "copy_id": "COPY-BOOK001-005",
                    "book_id": "BOOK001",
                    "copy_number": 5,
                    "status": "Lost",
                    "condition": "Lost",
                    "created_at": "2026-07-10 10:04:00",
                },
            }
        else:
            self.books["BOOK001"].update(
                {
                    "total_copies": 0,
                    "available_copies": 0,
                    "status": "Unavailable",
                }
            )

        self.update_history = []

    def collection(self, collection_name):
        assert collection_name == "books"

        return FakeBooksCollection(self)


def use_fake_database(monkeypatch, include_copies=True):
    fake_database = FakeDatabase(include_copies=include_copies)

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    return fake_database


def extract_copy_summary(response):
    html = response.get_data(as_text=True)

    matches = re.findall(
        (
            r'<span class="summary-number">\s*'
            r"(\d+)\s*</span>\s*"
            r'<span class="summary-label">\s*'
            r"([^<]+?)\s*</span>"
        ),
        html,
        re.DOTALL,
    )

    return {label.strip(): int(number) for number, label in matches}


# ============================================================
# SCRUM-895: ADD ADDITIONAL PHYSICAL COPIES
# ============================================================


def test_scrum_895_add_copies_page_loads(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/copies/add/BOOK001")

    assert response.status_code == 200
    assert b"Add Physical Book Copies" in response.data
    assert b"Python Programming" in response.data
    assert b"9780000000001" in response.data


def test_scrum_895_generates_sequential_copy_ids(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    assert response.status_code == 302

    copy_records = fake_database.copies["BOOK001"]

    assert "COPY-BOOK001-006" in copy_records
    assert "COPY-BOOK001-007" in copy_records
    assert len(copy_records) == 7


def test_scrum_895_redirects_to_book_details(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/books/details/BOOK001")


def test_scrum_895_new_copies_have_required_fields(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    first_new_copy = fake_database.copies["BOOK001"]["COPY-BOOK001-006"]

    second_new_copy = fake_database.copies["BOOK001"]["COPY-BOOK001-007"]

    assert first_new_copy["copy_id"] == ("COPY-BOOK001-006")
    assert first_new_copy["book_id"] == "BOOK001"
    assert first_new_copy["copy_number"] == 6
    assert first_new_copy["status"] == "Available"
    assert first_new_copy["condition"] == "Good"

    assert second_new_copy["copy_number"] == 7
    assert second_new_copy["status"] == "Available"
    assert second_new_copy["condition"] == "Good"

    datetime.strptime(
        first_new_copy["created_at"],
        "%Y-%m-%d %H:%M:%S",
    )


def test_scrum_895_updates_book_copy_counts(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    updated_book = fake_database.books["BOOK001"]

    assert updated_book["total_copies"] == 7
    assert updated_book["available_copies"] == 3
    assert updated_book["status"] == "Available"
    assert "updated_at" in updated_book


def test_scrum_895_preserves_existing_copy_records(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    original_copy = copy.deepcopy(fake_database.copies["BOOK001"]["COPY-BOOK001-001"])

    client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    assert fake_database.copies["BOOK001"]["COPY-BOOK001-001"] == original_copy


def test_scrum_895_generates_first_ids_when_no_copies_exist(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch,
        include_copies=False,
    )

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "2"},
    )

    assert response.status_code == 302

    assert set(fake_database.copies["BOOK001"].keys()) == {
        "COPY-BOOK001-001",
        "COPY-BOOK001-002",
    }

    updated_book = fake_database.books["BOOK001"]

    assert updated_book["total_copies"] == 2
    assert updated_book["available_copies"] == 2
    assert updated_book["status"] == "Available"


def test_scrum_895_rejects_non_numeric_quantity(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    copies_before = copy.deepcopy(fake_database.copies["BOOK001"])

    book_before = copy.deepcopy(fake_database.books["BOOK001"])

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "two"},
    )

    assert response.status_code == 400

    assert b"must be a valid whole number" in response.data

    assert fake_database.copies["BOOK001"] == copies_before

    assert fake_database.books["BOOK001"] == book_before


def test_scrum_895_rejects_zero_quantity(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    copies_before = copy.deepcopy(fake_database.copies["BOOK001"])

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "0"},
    )

    assert response.status_code == 400
    assert b"must be at least 1" in response.data

    assert fake_database.copies["BOOK001"] == copies_before


def test_scrum_895_rejects_negative_quantity(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    copies_before = copy.deepcopy(fake_database.copies["BOOK001"])

    response = client.post(
        "/books/copies/add/BOOK001",
        data={"quantity": "-3"},
    )

    assert response.status_code == 400
    assert b"must be at least 1" in response.data

    assert fake_database.copies["BOOK001"] == copies_before


def test_scrum_895_unknown_book_returns_404(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/copies/add/UNKNOWN")

    assert response.status_code == 404
    assert b"Book record not found." in response.data


# ============================================================
# SCRUM-898: VIEW BOOK DETAILS AND COPY SUMMARY
# ============================================================


def test_scrum_898_details_page_loads(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/BOOK001")

    assert response.status_code == 200
    assert b"Librarian Book Details" in response.data


def test_scrum_898_displays_complete_book_information(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/BOOK001")

    assert response.status_code == 200
    assert b"Python Programming" in response.data
    assert b"Sherman" in response.data
    assert b"9780000000001" in response.data
    assert b"Programming" in response.data
    assert b"Technology Press" in response.data
    assert b"2024" in response.data

    assert b"A beginner-friendly programming book." in response.data


def test_scrum_898_displays_correct_copy_summary(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/BOOK001")

    summary = extract_copy_summary(response)

    assert summary["Total Copies"] == 5
    assert summary["Available"] == 1
    assert summary["Borrowed"] == 1
    assert summary["Reserved"] == 1
    assert summary["Damaged"] == 1
    assert summary["Lost"] == 1


def test_scrum_898_displays_all_individual_copy_ids(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/BOOK001")

    assert response.status_code == 200

    for copy_number in range(1, 6):
        expected_copy_id = (f"COPY-BOOK001-{copy_number:03d}").encode()

        assert expected_copy_id in response.data


def test_scrum_898_displays_copy_statuses(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/BOOK001")

    assert b"Available" in response.data
    assert b"Borrowed" in response.data
    assert b"Reserved" in response.data
    assert b"Damaged" in response.data
    assert b"Lost" in response.data


def test_scrum_898_handles_book_with_no_copy_records(
    client,
    monkeypatch,
):
    use_fake_database(
        monkeypatch,
        include_copies=False,
    )

    response = client.get("/books/details/BOOK001")

    assert response.status_code == 200

    assert b"No physical-copy records found" in response.data


def test_scrum_898_unknown_book_returns_404(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/books/details/UNKNOWN")

    assert response.status_code == 404
    assert b"Book record not found." in response.data
