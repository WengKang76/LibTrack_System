import sys
import os
import pytest
from unittest.mock import MagicMock

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()

mock_firebase_config = MagicMock()
mock_firebase_config.db = MagicMock()
mock_firebase_config.COLLECTION_BOOKS = "books"
sys.modules["config.firebase_config"] = mock_firebase_config

from flask import Flask
from modules.book_catalogue.routes import book_bp

@pytest.fixture
def app():
    isolated_app = Flask(__name__)
    isolated_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "temporary-test-key-for-scrum12"
    })
    isolated_app.register_blueprint(book_bp)
    yield isolated_app

@pytest.fixture
def client(app):
    return app.test_client()
