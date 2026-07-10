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
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data

    def to_dict(self):
        return self._data.copy()


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
        app.register_blueprint(catalogue_routes.catalogue_bp)

        return app

    return create_app
