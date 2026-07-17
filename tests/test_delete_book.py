import modules.book_catalogue.routes as book_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data, reference=None):
        self.id = document_id
        self._data = data
        self.exists = data is not None
        self.reference = reference

    def to_dict(self):
        if self._data is None:
            return None
        return dict(self._data)


class FakeCopyDocumentReference:
    def __init__(self, database, book_id, copy_id):
        self.database = database
        self.book_id = book_id
        self.copy_id = copy_id
        self.id = copy_id

    def delete(self):
        self.database.copies.get(self.book_id, {}).pop(self.copy_id, None)


class FakeCopiesCollection:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id

    def stream(self):
        results = []
        for copy_id, data in self.database.copies.get(self.book_id, {}).items():
            reference = FakeCopyDocumentReference(
                self.database,
                self.book_id,
                copy_id,
            )
            results.append(
                FakeDocumentSnapshot(copy_id, data, reference=reference)
            )
        return results


class FakeBookDocumentReference:
    def __init__(self, database, book_id):
        self.database = database
        self.book_id = book_id
        self.id = book_id

    def get(self):
        return FakeDocumentSnapshot(
            self.book_id,
            self.database.books.get(self.book_id),
        )

    def collection(self, collection_name):
        assert collection_name == "copies"
        return FakeCopiesCollection(self.database, self.book_id)

    def delete(self):
        self.database.books.pop(self.book_id, None)
        self.database.copies.pop(self.book_id, None)


class FakeCollection:
    def __init__(self, database):
        self.database = database

    def document(self, document_id):
        return FakeBookDocumentReference(self.database, document_id)

    def stream(self):
        return [
            FakeDocumentSnapshot(document_id, data)
            for document_id, data in self.database.books.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.books = {
            "B001": {
                "title": "Python Programming",
                "author": "Sherman",
                "isbn": "9780000000001",
                "catalogue_status": "Active",
                "is_visible_to_students": True,
            }
        }
        self.copies = {
            "B001": {
                "COPY-B001-001": {
                    "copy_id": "COPY-B001-001",
                    "status": "Available",
                },
                "COPY-B001-002": {
                    "copy_id": "COPY-B001-002",
                    "status": "Borrowed",
                },
            }
        }

    def collection(self, collection_name):
        assert collection_name == "books"
        return FakeCollection(self)


def test_scrum_704_confirmation_page_loads(client, monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)

    response = client.get("/books/delete/B001")

    assert response.status_code == 200
    assert b"Delete Book Record" in response.data
    assert "B001" in fake_database.books


def test_scrum_704_delete_book_and_all_copies(client, monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)

    response = client.post("/books/delete/B001")

    assert response.status_code == 302
    assert "B001" not in fake_database.books
    assert "B001" not in fake_database.copies


def test_scrum_704_returns_to_book_list(client, monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)

    response = client.post("/books/delete/B001")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/books/")


def test_scrum_704_success_message_displayed(client, monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)

    response = client.post(
        "/books/delete/B001",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Book record deleted successfully." in response.data


def test_scrum_704_unknown_book_returns_404(client, monkeypatch):
    fake_database = FakeDatabase()
    monkeypatch.setattr(book_routes, "db", fake_database)

    response = client.get("/books/delete/UNKNOWN")

    assert response.status_code == 404
