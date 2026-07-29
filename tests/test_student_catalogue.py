import modules.student_catalogue.routes as student_routes


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


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def stream(self):
        return [
            FakeDocumentSnapshot(document_id, data)
            for document_id, data in self.records.items()
        ]

    def document(self, document_id):
        return FakeDocumentReference(
            self.records,
            document_id,
        )


class FakeDatabase:
    def __init__(self):
        self.books = {
            "B001": {
                "title": "Python Programming",
                "author": "Sherman",
                "isbn": "9780000000001",
                "category": "Programming",
                "publisher": "Technology Press",
                "publication_year": "2024",
                "total_copies": 5,
                "available_copies": 3,
                "status": "Available",
            }
        }

    def collection(self, collection_name):
        assert collection_name == "books"

        return FakeCollection(self.books)


def test_student_catalogue_page_loads(
    app,
    monkeypatch,
):
    app.register_blueprint(student_routes.student_catalogue_bp)

    fake_database = FakeDatabase()

    monkeypatch.setattr(
        student_routes,
        "db",
        fake_database,
    )

    client = app.test_client()

    response = client.get("/student/catalogue/")

    assert response.status_code == 200
    assert b"Explore Our Book Catalogue" in response.data
    assert b"Python Programming" in response.data
    assert b"View Book Details" in response.data


def test_student_book_details_page_loads(
    app,
    monkeypatch,
):
    app.register_blueprint(student_routes.student_catalogue_bp)

    fake_database = FakeDatabase()

    monkeypatch.setattr(
        student_routes,
        "db",
        fake_database,
    )

    client = app.test_client()

    response = client.get("/student/catalogue/details/B001")

    assert response.status_code == 200
    assert b"Python Programming" in response.data
    assert b"Sherman" in response.data
    assert b"9780000000001" in response.data
    assert b"Technology Press" in response.data


def test_student_catalogue_displays_availability(
    app,
    monkeypatch,
):
    app.register_blueprint(student_routes.student_catalogue_bp)

    fake_database = FakeDatabase()

    monkeypatch.setattr(
        student_routes,
        "db",
        fake_database,
    )

    client = app.test_client()

    response = client.get("/student/catalogue/")

    assert response.status_code == 200
    assert b"Available" in response.data


def test_student_unknown_book_returns_404(
    app,
    monkeypatch,
):
    app.register_blueprint(student_routes.student_catalogue_bp)

    fake_database = FakeDatabase()

    monkeypatch.setattr(
        student_routes,
        "db",
        fake_database,
    )

    client = app.test_client()

    response = client.get("/student/catalogue/details/UNKNOWN")

    assert response.status_code == 404
    assert b"Book record not found." in response.data
