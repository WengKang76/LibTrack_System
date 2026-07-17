from datetime import datetime
from pathlib import Path

import pytest
from flask import Flask

import modules.book_catalogue.routes as book_routes


BASE_DIR = Path(__file__).resolve().parents[1]


# ============================================================
# FAKE FIREBASE CLASSES
# ============================================================

class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None

        return dict(self._data)


class FakeDocumentReference:
    def __init__(self, records, document_id):
        self.records = records
        self.document_id = document_id

    def get(self):
        return FakeDocumentSnapshot(
            self.document_id,
            self.records.get(self.document_id),
        )

    def update(self, updated_data):
        if self.document_id not in self.records:
            raise KeyError("Book does not exist.")

        self.records[self.document_id].update(updated_data)


class FakeQuery:
    def __init__(
        self,
        records,
        field_name=None,
        expected_value=None,
    ):
        self.records = records
        self.field_name = field_name
        self.expected_value = expected_value
        self.maximum_results = None

    def where(self, field_name, operator, expected_value):
        assert operator == "=="

        return FakeQuery(
            self.records,
            field_name,
            expected_value,
        )

    def limit(self, number):
        self.maximum_results = number
        return self

    def stream(self):
        results = []

        for document_id, data in self.records.items():
            matches_query = (
                self.field_name is None
                or data.get(self.field_name) == self.expected_value
            )

            if matches_query:
                results.append(
                    FakeDocumentSnapshot(document_id, data)
                )

        if self.maximum_results is not None:
            results = results[:self.maximum_results]

        return results


class FakeCollection(FakeQuery):
    def document(self, document_id):
        return FakeDocumentReference(
            self.records,
            document_id,
        )


class FakeDB:
    def __init__(self):
        self.books = {
            "B001": {
                "title": "Python Programming",
                "author": "Original Author",
                "category": "Programming",
                "isbn": "123456789",
                "publisher": "Original Publisher",
                "publication_year": "2020",
                "total_copies": 5,
                "available_copies": 3,
                "status": "Available",
            },
            "B002": {
                "title": "Agile Software Development",
                "author": "Second Author",
                "category": "Software Engineering",
                "isbn": "999999999",
                "publisher": "Second Publisher",
                "publication_year": "2021",
                "total_copies": 2,
                "available_copies": 1,
                "status": "Available",
            },
        }

    def collection(self, collection_name):
        assert collection_name == "books"
        return FakeCollection(self.books)


# ============================================================
# FIXTURE
# ============================================================

@pytest.fixture
def book_client():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    app.config.update(
        TESTING=True,
        SECRET_KEY="testing-secret-key",
    )

    app.register_blueprint(book_routes.book_bp)

    return app.test_client()


def valid_edit_data():
    return {
        "title": "Updated Python Book",
        "author": "New Author",
        "category": "Programming",
        "isbn": "987654321",
        "publisher": "New Publisher",
        "publication_year": str(datetime.now().year),
    }


# ============================================================
# SCRUM-40 TESTS
# ============================================================

def test_scrum_40_manage_books_page_loads(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.get("/books/")

    assert response.status_code == 200
    assert b"Book Catalogue Management" in response.data
    assert b"Python Programming" in response.data
    assert b"Agile Software Development" in response.data


def test_scrum_40_manage_page_contains_edit_link(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.get("/books/")

    assert response.status_code == 200
    assert b"/books/edit/B001" in response.data
    assert b"/books/edit/B002" in response.data


def test_scrum_40_edit_book_page_loads(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.get("/books/edit/B001")

    assert response.status_code == 200
    assert b"Python Programming" in response.data
    assert b"Original Author" in response.data
    assert b"123456789" in response.data
    assert b"Save Changes" in response.data
    assert b"Cancel" in response.data


def test_scrum_40_edit_book_details_updated(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.post(
        "/books/edit/B001",
        data=valid_edit_data(),
    )

    updated_book = fake_db.books["B001"]

    assert response.status_code == 302
    assert updated_book["title"] == "Updated Python Book"
    assert updated_book["author"] == "New Author"
    assert updated_book["isbn"] == "987654321"
    assert updated_book["publisher"] == "New Publisher"
    assert "updated_at" in updated_book


def test_scrum_40_returns_to_list_after_update(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.post(
        "/books/edit/B001",
        data=valid_edit_data(),
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/books/")


def test_scrum_40_success_message_displayed(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.post(
        "/books/edit/B001",
        data=valid_edit_data(),
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        b"Book details updated successfully."
        in response.data
    )

    assert b"Updated Python Book" in response.data


def test_scrum_40_reject_empty_book_title(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()
    submitted_data["title"] = ""

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 400

    assert (
        b"Please fill in all required fields."
        in response.data
    )

    assert (
        fake_db.books["B001"]["title"]
        == "Python Programming"
    )


def test_scrum_40_reject_empty_author(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()
    submitted_data["author"] = ""

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 400

    assert (
        b"Please fill in all required fields."
        in response.data
    )


def test_scrum_40_reject_duplicate_isbn(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()

    # This ISBN belongs to B002.
    submitted_data["isbn"] = "999999999"

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 400

    assert (
        b"A book with this ISBN already exists."
        in response.data
    )

    assert fake_db.books["B001"]["isbn"] == "123456789"


def test_scrum_40_allows_current_isbn(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()
    submitted_data["isbn"] = "123456789"

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 302
    assert fake_db.books["B001"]["isbn"] == "123456789"


def test_scrum_40_reject_invalid_publication_year(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()
    submitted_data["publication_year"] = "abcd"

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 400

    assert (
        b"Publication year must be a valid four-digit year."
        in response.data
    )


def test_scrum_40_reject_future_publication_year(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    submitted_data = valid_edit_data()

    submitted_data["publication_year"] = str(
        datetime.now().year + 1
    )

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    assert response.status_code == 400
    assert b"Publication year must be between" in response.data


def test_scrum_40_unknown_book_returns_404(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    response = book_client.get(
        "/books/edit/UNKNOWN"
    )

    assert response.status_code == 404
    assert b"Book record not found." in response.data


def test_scrum_40_does_not_change_copy_or_status_fields(
    book_client,
    monkeypatch,
):
    fake_db = FakeDB()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_db,
    )

    original_total = fake_db.books["B001"]["total_copies"]
    original_available = fake_db.books["B001"]["available_copies"]
    original_status = fake_db.books["B001"]["status"]

    submitted_data = valid_edit_data()

    # These values should be ignored by SCRUM-40.
    submitted_data["total_copies"] = "100"
    submitted_data["available_copies"] = "90"
    submitted_data["status"] = "Unavailable"

    response = book_client.post(
        "/books/edit/B001",
        data=submitted_data,
    )

    updated_book = fake_db.books["B001"]

    assert response.status_code == 302
    assert updated_book["total_copies"] == original_total
    assert updated_book["available_copies"] == original_available
    assert updated_book["status"] == original_status