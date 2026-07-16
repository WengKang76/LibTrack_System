import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest
from flask import Flask


# Project root:
# C:\Users\sherm\Downloads\library_system\LibTrack_System
BASE_DIR = Path(__file__).resolve().parents[1]

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# Prevent automated tests from connecting to real Firebase.
fake_firebase_config = ModuleType(
    "config.firebase_config"
)
fake_firebase_config.db = MagicMock()
fake_firebase_config.COLLECTION_BOOKS = "books"
fake_firebase_config.COLLECTION_USERS = "users"

sys.modules[
    "config.firebase_config"
] = fake_firebase_config


from modules.book_catalogue.routes import book_bp
from modules.user_management.routes import (
    user_management_bp,
)


@pytest.fixture
def app():
    test_app = Flask(
        "test_app",
        template_folder=str(
            BASE_DIR / "templates"
        ),
        static_folder=str(
            BASE_DIR / "static"
        ),
    )

    test_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
    )

    # base.html contains links to both blueprints.
    # Therefore both must be registered in the test app.
    test_app.register_blueprint(book_bp)
    test_app.register_blueprint(
        user_management_bp
    )

    return test_app


@pytest.fixture
def client(app):
    return app.test_client()
