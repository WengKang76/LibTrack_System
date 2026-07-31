import time

import pytest
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

import modules.authentication.routes as auth_routes


TEST_USER_ID = "USR100"
TEST_EMAIL = "student100@tarumt.edu.my"
OLD_PASSWORD = "OldPassword@123"
NEW_PASSWORD = "NewPassword@123"

GENERIC_RESET_MESSAGE = (
    b"If an account exists for this email address"
)


# ============================================================
# FAKE FIRESTORE
# ============================================================

class FakeUserDocumentReference:
    def __init__(
        self,
        database,
        document_id,
    ):
        self.database = database
        self.document_id = document_id

    def update(self, updated_data):
        if self.document_id not in self.database.users:
            raise KeyError(
                f"Unknown user: {self.document_id}"
            )

        self.database.users[
            self.document_id
        ].update(dict(updated_data))

        self.database.update_history.append(
            {
                "document_id": self.document_id,
                "updated_data": dict(updated_data),
            }
        )


class FakeUsersCollection:
    def __init__(self, database):
        self.database = database

    def document(self, document_id):
        return FakeUserDocumentReference(
            self.database,
            document_id,
        )


class FakeDatabase:
    def __init__(self, user):
        self.users = {
            user["document_id"]: user,
        }

        self.update_history = []

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(self)


# ============================================================
# FIXTURES AND HELPERS
# ============================================================

@pytest.fixture
def password_reset_environment(
    app,
    client,
    monkeypatch,
):
    user = {
        "document_id": TEST_USER_ID,
        "user_id": TEST_USER_ID,
        "full_name": "Test Student",
        "email": TEST_EMAIL,
        "role": "Student",
        "account_status": "Active",
        "password_hash": generate_password_hash(
            OLD_PASSWORD
        ),
        "password_reset_version": 0,
    }

    fake_database = FakeDatabase(user)

    monkeypatch.setattr(
        auth_routes,
        "db",
        fake_database,
    )

    def fake_find_user_by_email(email):
        normalised_email = str(
            email or ""
        ).strip().lower()

        if normalised_email == TEST_EMAIL:
            return user

        return None

    monkeypatch.setattr(
        auth_routes,
        "_find_user_by_email",
        fake_find_user_by_email,
    )

    app.config.update(
        PASSWORD_RESET_TOKEN_MAX_AGE=900,
        SHOW_PASSWORD_RESET_LINK=True,
    )

    return {
        "app": app,
        "client": client,
        "user": user,
        "database": fake_database,
    }


def generate_reset_token(app, user):
    with app.app_context():
        return (
            auth_routes
            ._generate_password_reset_token(
                user
            )
        )


# ============================================================
# SCRUM-1179: FORGOT PASSWORD PAGE
# ============================================================

def test_forgot_password_page_loads(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.get(
        "/auth/forgot-password"
    )

    assert response.status_code == 200
    assert b"Forgot Password" in response.data
    assert b"Email Address" in response.data
    assert b"Generate Reset Link" in response.data


def test_forgot_password_rejects_empty_email(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.post(
        "/auth/forgot-password",
        data={
            "email": "",
        },
    )

    assert response.status_code == 400
    assert (
        b"Email address is required"
        in response.data
    )


def test_forgot_password_rejects_invalid_email(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.post(
        "/auth/forgot-password",
        data={
            "email": "invalid-email",
        },
    )

    assert response.status_code == 400
    assert (
        b"Enter a valid email address"
        in response.data
    )


def test_registered_email_receives_generic_message(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.post(
        "/auth/forgot-password",
        data={
            "email": TEST_EMAIL,
        },
    )

    assert response.status_code == 200
    assert (
        GENERIC_RESET_MESSAGE
        in response.data
    )


def test_unknown_email_receives_same_generic_message(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.post(
        "/auth/forgot-password",
        data={
            "email": "unknown@tarumt.edu.my",
        },
    )

    assert response.status_code == 200
    assert (
        GENERIC_RESET_MESSAGE
        in response.data
    )

    # An unknown account must not receive a reset URL.
    assert (
        b"/auth/reset-password/"
        not in response.data
    )


def test_registered_email_generates_reset_link(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.post(
        "/auth/forgot-password",
        data={
            "email": TEST_EMAIL,
        },
    )

    assert response.status_code == 200

    assert (
        b"/auth/reset-password/"
        in response.data
    )

    assert (
        b"Set New Password"
        in response.data
    )

    assert (
        b'name="password"'
        in response.data
    )

    assert (
        b'name="confirm_password"'
        in response.data
    )

    assert (
        b"Reset Password"
        in response.data
    )


# ============================================================
# RESET TOKEN VALIDATION
# ============================================================

def test_valid_reset_token_loads_form(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.get(
        f"/auth/reset-password/{token}"
    )

    assert response.status_code == 200
    assert b"Reset Password" in response.data
    assert (
        b'name="password"'
        in response.data
    )
    assert (
        b'name="confirm_password"'
        in response.data
    )


def test_invalid_reset_token_is_rejected(
    password_reset_environment,
):
    client = password_reset_environment[
        "client"
    ]

    response = client.get(
        "/auth/reset-password/"
        "invalid-reset-token"
    )

    assert response.status_code == 400
    assert (
        b"Invalid Reset Link"
        in response.data
    )


def test_expired_reset_token_is_rejected(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    app.config[
        "PASSWORD_RESET_TOKEN_MAX_AGE"
    ] = 0

    token = generate_reset_token(
        app,
        user,
    )

    # itsdangerous timestamps use seconds.
    time.sleep(1.1)

    response = client.get(
        f"/auth/reset-password/{token}"
    )

    assert response.status_code == 400
    assert (
        b"Invalid Reset Link"
        in response.data
    )


# ============================================================
# NEW PASSWORD VALIDATION
# ============================================================

def test_reset_rejects_empty_password(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": "",
            "confirm_password": "",
        },
    )

    assert response.status_code == 400
    assert (
        b"New password is required"
        in response.data
    )
    assert (
        b"Password confirmation is required"
        in response.data
    )


def test_reset_rejects_weak_password(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    original_hash = user["password_hash"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": "weak",
            "confirm_password": "weak",
        },
    )

    assert response.status_code == 400
    assert (
        user["password_hash"]
        == original_hash
    )


def test_reset_rejects_password_mismatch(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    original_hash = user["password_hash"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": (
                "DifferentPassword@123"
            ),
        },
    )

    assert response.status_code == 400
    assert (
        b"do not match"
        in response.data
    )
    assert (
        user["password_hash"]
        == original_hash
    )


def test_reset_rejects_current_password_reuse(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    original_hash = user["password_hash"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": OLD_PASSWORD,
            "confirm_password": OLD_PASSWORD,
        },
    )

    assert response.status_code == 400
    assert (
        b"must be different"
        in response.data
    )
    assert (
        user["password_hash"]
        == original_hash
    )


# ============================================================
# SUCCESSFUL PASSWORD RESET
# ============================================================

def test_valid_password_reset_updates_hash(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]
    database = password_reset_environment[
        "database"
    ]

    original_hash = user["password_hash"]

    token = generate_reset_token(
        app,
        user,
    )

    response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 302
    assert (
        "/auth/login"
        in response.headers["Location"]
    )

    assert (
        user["password_hash"]
        != original_hash
    )

    assert check_password_hash(
        user["password_hash"],
        NEW_PASSWORD,
    )

    assert not check_password_hash(
        user["password_hash"],
        OLD_PASSWORD,
    )

    assert len(
        database.update_history
    ) == 1


def test_successful_reset_increments_reset_version(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    token = generate_reset_token(
        app,
        user,
    )

    client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert (
        user["password_reset_version"]
        == 1
    )


def test_successful_reset_clears_session(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    with client.session_transaction() as session:
        session["user_id"] = TEST_USER_ID
        session["email"] = TEST_EMAIL
        session["role"] = "student"

    token = generate_reset_token(
        app,
        user,
    )

    client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "email" not in session
        assert "role" not in session


def test_used_reset_token_cannot_be_reused(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    token = generate_reset_token(
        app,
        user,
    )

    first_response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert first_response.status_code == 302

    second_response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": "AnotherPassword@123",
            "confirm_password": (
                "AnotherPassword@123"
            ),
        },
    )

    assert second_response.status_code == 400
    assert (
        b"Invalid Reset Link"
        in second_response.data
    )


def test_new_password_can_be_used_for_login(
    password_reset_environment,
):
    app = password_reset_environment["app"]
    client = password_reset_environment[
        "client"
    ]
    user = password_reset_environment["user"]

    token = generate_reset_token(
        app,
        user,
    )

    reset_response = client.post(
        f"/auth/reset-password/{token}",
        data={
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert reset_response.status_code == 302

    old_password_response = client.post(
        "/auth/login",
        data={
            "email": TEST_EMAIL,
            "password": OLD_PASSWORD,
        },
    )

    assert old_password_response.status_code != 302
    assert (
        b"Invalid email or password"
        in old_password_response.data
    )

    new_password_response = client.post(
        "/auth/login",
        data={
            "email": TEST_EMAIL,
            "password": NEW_PASSWORD,
        },
    )

    assert new_password_response.status_code == 302