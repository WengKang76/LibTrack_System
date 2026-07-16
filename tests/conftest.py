from pathlib import Path
import sys
import types

import pytest
from flask import Flask

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Prevent automated tests from loading the real Firebase credential file.
import config

fake_firebase_config = types.ModuleType("config.firebase_config")
fake_firebase_config.db = None
fake_firebase_config.COLLECTION_BOOKS = "books"
fake_firebase_config.COLLECTION_USERS = "users"
fake_firebase_config.COLLECTION_BORROW_REQUESTS = "borrow_requests"
fake_firebase_config.COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"
fake_firebase_config.COLLECTION_PENALTIES = "penalties"
fake_firebase_config.COLLECTION_RESERVATIONS = "reservations"
sys.modules["config.firebase_config"] = fake_firebase_config
setattr(config, "firebase_config", fake_firebase_config)

from modules.catalogue_reservation import routes as catalogue_routes


COLLECTION_ID_FIELDS = {
    "books": "book_id",
    "reservations": "reservation_id",
    "borrow_requests": "request_id",
}


class FakeDocument:
    def __init__(self, document_id, data=None, exists=True):
        self.id = document_id
        self._data = data or {}
        self.exists = exists

    def to_dict(self):
        return self._data.copy()


class FakeDocumentReference:
    def __init__(self, collection_name, document_id, database):
        self._collection_name = collection_name
        self._document_id = document_id
        self._database = database

    @property
    def _id_field(self):
        return COLLECTION_ID_FIELDS[self._collection_name]

    def get(self):
        records = self._database.collections[self._collection_name]

        for record in records:
            if record.get(self._id_field) == self._document_id:
                copied_record = record.copy()
                copied_record.pop(self._id_field, None)
                return FakeDocument(
                    self._document_id,
                    copied_record,
                    exists=True,
                )

        return FakeDocument(self._document_id, {}, exists=False)

    def update(self, changes):
        records = self._database.collections[self._collection_name]

        for record in records:
            if record.get(self._id_field) == self._document_id:
                record.update(changes)
                return

        raise ValueError(f"Document not found: {self._document_id}")


class FakeQuery:
    def __init__(self, collection, filters=None):
        self._collection = collection
        self._filters = filters or []

    def where(self, field_name, operator, expected_value):
        if operator != "==":
            raise ValueError(f"Unsupported operator: {operator}")

        return FakeQuery(
            self._collection,
            self._filters + [(field_name, expected_value)],
        )

    def stream(self):
        documents = self._collection.stream()

        return [
            document
            for document in documents
            if all(
                document.to_dict().get(field_name) == expected_value
                for field_name, expected_value in self._filters
            )
        ]


class FakeCollection:
    def __init__(self, collection_name, database):
        self._collection_name = collection_name
        self._database = database

    @property
    def _id_field(self):
        return COLLECTION_ID_FIELDS[self._collection_name]

    @property
    def records(self):
        return self._database.collections[self._collection_name]

    def stream(self):
        documents = []

        for index, record in enumerate(self.records, start=1):
            copied_record = record.copy()
            document_id = copied_record.pop(
                self._id_field,
                f"{self._collection_name[:1].upper()}{index:03d}",
            )
            documents.append(FakeDocument(document_id, copied_record))

        return documents

    def document(self, document_id):
        return FakeDocumentReference(
            self._collection_name,
            document_id,
            self._database,
        )

    def where(self, field_name, operator, expected_value):
        return FakeQuery(self).where(field_name, operator, expected_value)

    def add(self, data):
        prefix = {
            "books": "B",
            "reservations": "R",
            "borrow_requests": "BR",
        }[self._collection_name]

        document_id = f"{prefix}{len(self.records) + 1:03d}"
        stored_record = data.copy()
        stored_record[self._id_field] = document_id
        self.records.append(stored_record)

        return (
            None,
            FakeDocumentReference(
                self._collection_name,
                document_id,
                self._database,
            ),
        )


class FakeFirestore:
    def __init__(self, books=None, reservations=None, borrow_requests=None):
        self.collections = {
            "books": [book.copy() for book in (books or [])],
            "reservations": [
                reservation.copy()
                for reservation in (reservations or [])
            ],
            "borrow_requests": [
                borrow_request.copy()
                for borrow_request in (borrow_requests or [])
            ],
        }

    def collection(self, collection_name):
        if collection_name not in self.collections:
            raise ValueError(f"Unexpected collection: {collection_name}")

        return FakeCollection(collection_name, self)


@pytest.fixture
def app_factory(monkeypatch):
    def create_app(books=None, reservations=None, borrow_requests=None):
        fake_db = FakeFirestore(
            books=books,
            reservations=reservations,
            borrow_requests=borrow_requests,
        )
        monkeypatch.setattr(catalogue_routes, "db", fake_db)

        app = Flask(
            "libtrack_test",
            template_folder=str(PROJECT_ROOT / "templates"),
            static_folder=str(PROJECT_ROOT / "static"),
        )
        app.config.update(
            TESTING=True,
            SECRET_KEY="automated-test-secret-key",
        )
        app.extensions["fake_firestore"] = fake_db

        @app.route("/")
        def home():
            return "LibTrack Test Home"

        app.register_blueprint(catalogue_routes.catalogue_bp)

        return app

    return create_app
