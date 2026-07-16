from copy import deepcopy
from datetime import datetime

import modules.book_catalogue.routes as book_routes


class FakeSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None
        return dict(self._data)


class FakeCopyReference:
    def __init__(self, database, book_id, copy_id):
        self.database = database
        self.book_id = book_id
        self.copy_id = copy_id
        self.id = copy_id

    def get(self):
        return FakeSnapshot(
            self.copy_id,
            self.database.copies.get(
                self.book_id,
                {},
            ).get(self.copy_id),
        )

    def update(self, data):
        self.database.copies[
            self.book_id
        ][self.copy_id].update(dict(data))


class FakeCopiesCollection:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id

    def document(self, copy_id):
        return FakeCopyReference(
            self.database,
            self.book_id,
            copy_id,
        )

    def stream(self):
        return [
            FakeSnapshot(copy_id, data)
            for copy_id, data
            in self.database.copies.get(
                self.book_id,
                {},
            ).items()
        ]


class FakeBookReference:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id
        self.id = book_id

    def get(self):
        return FakeSnapshot(
            self.book_id,
            self.database.books.get(self.book_id),
        )

    def update(self, data):
        self.database.books[self.book_id].update(
            dict(data)
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
        return FakeBookReference(
            self.database,
            book_id,
        )

    def stream(self):
        return [
            FakeSnapshot(book_id, data)
            for book_id, data
            in self.database.books.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.books = {
            "BOOK001": {
                "title": "Old Programming Guide",
                "author": "Sherman",
                "isbn": "9780000000001",
                "category": "Programming",
                "total_copies": 3,
                "available_copies": 2,
                "status": "Available",
                "catalogue_status": "Active",
                "is_visible_to_students": True,
                "catalogue_inactive_reason": "",
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
                },
                "COPY-BOOK001-002": {
                    "copy_id": "COPY-BOOK001-002",
                    "book_id": "BOOK001",
                    "copy_number": 2,
                    "status": "Available",
                    "condition": "Good",
                },
                "COPY-BOOK001-003": {
                    "copy_id": "COPY-BOOK001-003",
                    "book_id": "BOOK001",
                    "copy_number": 3,
                    "status": "Damaged",
                    "condition": "Damaged",
                },
            }
        }

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


def test_deactivate_book_page_loads(client, monkeypatch):
    use_fake_database(monkeypatch)

    response = client.get(
        "/books/catalogue/deactivate/BOOK001"
    )

    assert response.status_code == 200
    assert b"Deactivate Book" in response.data
    assert b"Outdated Content" in response.data


def test_deactivate_book_hides_title_without_changing_copies(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)
    copies_before = deepcopy(
        fake_database.copies["BOOK001"]
    )

    response = client.post(
        "/books/catalogue/deactivate/BOOK001",
        data={"reason": "Outdated Content"},
    )

    assert response.status_code == 302
    book = fake_database.books["BOOK001"]
    assert book["catalogue_status"] == "Inactive"
    assert book["is_visible_to_students"] is False
    assert (
        book["catalogue_inactive_reason"]
        == "Outdated Content"
    )
    assert fake_database.copies["BOOK001"] == copies_before
    assert book["total_copies"] == 3
    assert book["available_copies"] == 2


def test_deactivate_book_rejects_invalid_reason(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post(
        "/books/catalogue/deactivate/BOOK001",
        data={"reason": "Random Reason"},
    )

    assert response.status_code == 400
    assert (
        fake_database.books["BOOK001"][
            "catalogue_status"
        ]
        == "Active"
    )


def test_activate_book_makes_title_visible_again(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)
    fake_database.books["BOOK001"].update(
        {
            "catalogue_status": "Inactive",
            "is_visible_to_students": False,
            "catalogue_inactive_reason": (
                "Outdated Content"
            ),
        }
    )

    response = client.post(
        "/books/catalogue/activate/BOOK001"
    )

    assert response.status_code == 302
    book = fake_database.books["BOOK001"]
    assert book["catalogue_status"] == "Active"
    assert book["is_visible_to_students"] is True
    assert book["catalogue_inactive_reason"] == ""


def test_activate_already_active_book_returns_400(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post(
        "/books/catalogue/activate/BOOK001"
    )

    assert response.status_code == 400
    assert b"already active" in response.data


def test_restore_damaged_copy_returns_it_to_available(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post(
        "/books/copies/restore/"
        "BOOK001/COPY-BOOK001-003"
    )

    assert response.status_code == 302
    copy_record = fake_database.copies[
        "BOOK001"
    ]["COPY-BOOK001-003"]
    assert copy_record["status"] == "Available"
    assert copy_record["condition"] == "Good"
    datetime.strptime(
        copy_record["restored_at"],
        "%Y-%m-%d %H:%M:%S",
    )

    book = fake_database.books["BOOK001"]
    assert book["available_copies"] == 3
    assert book["total_copies"] == 3
    assert book["status"] == "Available"
    assert book["catalogue_status"] == "Active"


def test_restore_non_damaged_copy_returns_400(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post(
        "/books/copies/restore/"
        "BOOK001/COPY-BOOK001-001"
    )

    assert response.status_code == 400
    assert (
        fake_database.copies["BOOK001"]
        ["COPY-BOOK001-001"]["status"]
        == "Available"
    )


def test_deactivate_and_activate_changes_student_catalogue_visibility(
    app,
    monkeypatch,
):
    import modules.student_catalogue.routes as student_routes

    app.register_blueprint(
        student_routes.student_catalogue_bp
    )
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)
    monkeypatch.setattr(student_routes, "db", fake_database)
    client = app.test_client()

    before = client.get("/student/catalogue/")
    assert b"Old Programming Guide" in before.data

    deactivate_response = client.post(
        "/books/catalogue/deactivate/BOOK001",
        data={"reason": "Outdated Content"},
    )
    assert deactivate_response.status_code == 302

    hidden = client.get("/student/catalogue/")
    assert b"Old Programming Guide" not in hidden.data

    direct_details = client.get(
        "/student/catalogue/details/BOOK001"
    )
    assert direct_details.status_code == 404

    activate_response = client.post(
        "/books/catalogue/activate/BOOK001"
    )
    assert activate_response.status_code == 302

    visible_again = client.get("/student/catalogue/")
    assert b"Old Programming Guide" in visible_again.data
