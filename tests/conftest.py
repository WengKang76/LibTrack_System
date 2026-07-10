import os
import sys
from pathlib import Path

import pytest
from flask import Flask

# Prevent real Firebase connection during testing
os.environ["TESTING"] = "1"

# Add project root to Python path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from modules.penalty_transaction.routes import penalty_bp


@pytest.fixture
def client():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static")
    )

    app.secret_key = "test-secret-key"
    app.config["TESTING"] = True

    # Only test your penalty module
    app.register_blueprint(penalty_bp)

    with app.test_client() as client:
        yield client