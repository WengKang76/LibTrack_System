import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from flask import Flask

# Prevent real Firebase connection during testing
os.environ["TESTING"] = "1"

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# Fake Firebase config for automated tests
fake_firebase_config = ModuleType("config.firebase_config")
fake_firebase_config.db = MagicMock()

fake_firebase_config.COLLECTION_BOOKS = "books"
fake_firebase_config.COLLECTION_USERS = "users"
fake_firebase_config.COLLECTION_BORROW_REQUESTS = "borrow_requests"
fake_firebase_config.COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"
fake_firebase_config.COLLECTION_PENALTIES = "penalties"
fake_firebase_config.COLLECTION_RESERVATIONS = "reservations"

sys.modules["config.firebase_config"] = fake_firebase_config


from modules.penalty_transaction.routes import penalty_bp
from modules.book_catalogue.routes import book_bp
from modules.student_catalogue.routes import student_catalogue_bp
from modules.user_management.routes import user_management_bp


@pytest.fixture
def app():
    test_app = Flask(
        "test_app",
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    test_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    test_app.register_blueprint(penalty_bp)
    test_app.register_blueprint(book_bp)
    test_app.register_blueprint(student_catalogue_bp)
    test_app.register_blueprint(user_management_bp)

    return test_app


@pytest.fixture
def client(app):
    return app.test_client()