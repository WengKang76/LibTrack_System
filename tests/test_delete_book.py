import modules.book_catalogue.routes as book_routes

class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data

    def to_dict(self):
        return dict(self._data)
    
class FakeDocumentReference:
    def __init__(self, records, document_id):
        self.records = records
        self.document_id = document_id

    def delete(self):
        self.records.pop(self.document_id, None)


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def document(self, document_id):
        return FakeDocumentReference(
            self.records,
            document_id,
        )

    def stream(self):
        return [
            FakeDocumentSnapshot(document_id, data)
            for document_id, data in self.records.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.books = {
            "B001": {
                "title": "Python Programming",
                "author": "Sherman",
                "isbn": "9780000000001",
            }
        }

    def collection(self, collection_name):
        assert collection_name == "books"
        return FakeCollection(self.books)


def test_scrum_704_delete_book(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    response = client.get("/books/delete/B001")

    assert response.status_code == 302
    assert "B001" not in fake_database.books


def test_scrum_704_returns_to_book_list(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    response = client.get("/books/delete/B001")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/books/")


def test_scrum_704_success_message_displayed(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    response = client.get(
        "/books/delete/B001",
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        b"Book record deleted successfully."
        in response.data
    )