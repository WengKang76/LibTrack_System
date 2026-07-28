import pytest
import time
from werkzeug.security import (
    generate_password_hash,
)

import modules.authentication.routes as auth_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None

        return dict(self._data)


class FakeUsersCollection:
    def __init__(self, database):
        self.database = database

    def stream(self):
        return [
            FakeDocumentSnapshot(
                document_id,
                user,
            )
            for document_id, user
            in self.database.users.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.users = {
            "USR001": {
                "user_id": "USR001",
                "full_name": "Active Student",
                "email": "student@demo.com",
                "password_hash": (
                    generate_password_hash(
                        "Student@123"
                    )
                ),
                "role": "Student",
                "account_status": "Active",
            },
            "USR002": {
                "user_id": "USR002",
                "full_name": "Inactive Student",
                "email": "inactive@demo.com",
                "password_hash": (
                    generate_password_hash(
                        "Inactive@123"
                    )
                ),
                "role": "Student",
                "account_status": "Inactive",
            },
            "USR003": {
                "user_id": "USR003",
                "full_name": "Demo Librarian",
                "email": "librarian@demo.com",
                "password_hash": (
                    generate_password_hash(
                        "Librarian@123"
                    )
                ),
                "role": "Librarian",
                "account_status": "Active",
            },
        }

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(self)


@pytest.fixture
def login_database(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        auth_routes,
        "db",
        fake_database,
    )

    return fake_database


def test_login_page_loads(
    client,
    login_database,
):
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert b"Login to LibTrack" in response.data
    assert b"Show password" in response.data


def test_active_student_can_log_in(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "student@demo.com",
            "password": "Student@123",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
    "/"
)

    with client.session_transaction() as session:
        assert session["user_id"] == "USR001"
        assert session["role"] == "student"
        assert session["full_name"] == (
            "Active Student"
        )


def test_active_librarian_can_log_in(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "librarian@demo.com",
            "password": "Librarian@123",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
    "/"
)

    with client.session_transaction() as session:
        assert session["user_id"] == "USR003"
        assert session["role"] == "librarian"


def test_incorrect_password_is_rejected(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "student@demo.com",
            "password": "WrongPassword@123",
        },
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_unknown_email_is_rejected(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "unknown@demo.com",
            "password": "Student@123",
        },
    )

    assert response.status_code == 401
    assert b"Invalid email or password." in response.data


def test_inactive_student_cannot_log_in(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "inactive@demo.com",
            "password": "Inactive@123",
        },
    )

    assert response.status_code == 403

    assert (
        b"Your account is currently inactive."
        in response.data
    )

    with client.session_transaction() as session:
        assert "user_id" not in session


def test_email_login_is_case_insensitive(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "STUDENT@DEMO.COM",
            "password": "Student@123",
        },
    )

    assert response.status_code == 302


def test_login_requires_email_and_password(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "",
            "password": "",
        },
    )

    assert response.status_code == 400

    assert (
        b"Email and password are required."
        in response.data
    )


def test_logout_clears_authenticated_session(
    client,
    login_database,
):
    client.post(
        "/auth/login",
        data={
            "email": "student@demo.com",
            "password": "Student@123",
        },
    )

    response = client.post("/auth/logout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/auth/login"
    )

    with client.session_transaction() as session:
        assert "user_id" not in session
        assert "role" not in session
        assert "email" not in session


def test_login_page_has_show_password_control(
    client,
    login_database,
):
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert b'id="show_password"' in response.data
    assert b'id="password"' in response.data


def test_successful_login_creates_permanent_session(
    client,
    login_database,
):
    response = client.post(
        "/auth/login",
        data={
            "email": "student@demo.com",
            "password": "Student@123",
        },
    )

    assert response.status_code == 302

    with client.session_transaction() as user_session:
        assert user_session.permanent is True
        assert "last_activity" in user_session


def test_session_security_configuration(app):
    assert (
        app.permanent_session_lifetime.total_seconds()
        == 1800
    )

    assert (
        app.config["SESSION_COOKIE_HTTPONLY"]
        is True
    )

    assert (
        app.config["SESSION_COOKIE_SAMESITE"]
        == "Lax"
    )

    assert (
        app.config["SESSION_REFRESH_EACH_REQUEST"]
        is True
    )


def test_expired_session_is_cleared(
    client,
):
    with client.session_transaction() as user_session:
        user_session["user_id"] = "USR001"
        user_session["full_name"] = "Expired User"
        user_session["email"] = "expired@demo.com"
        user_session["role"] = "student"

        user_session["last_activity"] = (
            time.time() - 1900
        )

        user_session.permanent = True

    response = client.get(
        "/auth/register",
        follow_redirects=False,
    )

    assert response.status_code == 302

    assert response.headers["Location"].endswith(
        "/auth/login"
    )

    with client.session_transaction() as user_session:
        assert "user_id" not in user_session
        assert "role" not in user_session
        assert "email" not in user_session
        assert "last_activity" not in user_session


def test_expired_session_displays_message(
    client,
):
    with client.session_transaction() as user_session:
        user_session["user_id"] = "USR001"
        user_session["role"] = "student"

        user_session["last_activity"] = (
            time.time() - 1900
        )

        user_session.permanent = True

    response = client.get(
        "/auth/register",
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert (
        b"Your session has expired due to inactivity."
        in response.data
    )


def test_active_session_updates_last_activity(
    client,
):
    old_activity_time = time.time() - 60

    with client.session_transaction() as user_session:
        user_session["user_id"] = "USR001"
        user_session["full_name"] = "Active User"
        user_session["role"] = "student"
        user_session["last_activity"] = (
            old_activity_time
        )
        user_session.permanent = True

    response = client.get("/auth/register")

    assert response.status_code == 200

    with client.session_transaction() as user_session:
        assert (
            user_session["last_activity"]
            > old_activity_time
        )