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
sys.modules["config.firebase_config"] = fake_firebase_config
setattr(config, "firebase_config", fake_firebase_config)

from modules.catalogue_reservation import routes as catalogue_routes


class FakeDocument:
    def __init__(self, document_id, data=None, exists=True):
        self.id = document_id
        self._data = data or {}
        self.exists = exists

    def to_dict(self):
        return self._data.copy()


class FakeDocumentReference:
    def __init__(self, document_id, books):
        self._document_id = document_id
        self._books = books

    def get(self):
        for book in self._books:
            if book.get("book_id") == self._document_id:
                copied_book = book.copy()
                copied_book.pop("book_id", None)
                return FakeDocument(
                    self._document_id,
                    copied_book,
                    exists=True
                )

        return FakeDocument(
            self._document_id,
            {},
            exists=False
        )


class FakeCollection:
    def __init__(self, books):
        self._books = books

    def stream(self):
        documents = []

        for index, book in enumerate(self._books, start=1):
            copied_book = book.copy()
            document_id = copied_book.pop("book_id", f"B{index:03d}")
            documents.append(FakeDocument(document_id, copied_book))

        return documents

    def document(self, document_id):
        return FakeDocumentReference(document_id, self._books)


class FakeFirestore:
    def __init__(self, books):
        self._books = books

    def collection(self, collection_name):
        if collection_name != "books":
            raise ValueError(f"Unexpected collection: {collection_name}")

        return FakeCollection(self._books)


@pytest.fixture
def app_factory(monkeypatch):
    def create_app(books=None):
        fake_db = FakeFirestore(books or [])
        monkeypatch.setattr(catalogue_routes, "db", fake_db)

        app = Flask(
            "libtrack_test",
            template_folder=str(PROJECT_ROOT / "templates"),
            static_folder=str(PROJECT_ROOT / "static")
        )
        app.config.update(
            TESTING=True,
            SECRET_KEY="automated-test-secret-key"
        )

        @app.route("/")
        def home():
            return "LibTrack Test Home"

        app.register_blueprint(catalogue_routes.catalogue_bp)

        return app

    return create_app
