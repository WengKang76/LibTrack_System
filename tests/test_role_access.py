import pytest
from flask import Flask

from modules.authentication.decorators import (
    librarian_required,
    login_required,
    student_or_librarian_required,
    student_required,
)


@pytest.fixture
def role_app():
    application = Flask(__name__)

    application.config.update(
        TESTING=True,
        SECRET_KEY="role-access-test-key",
    )

    @application.route("/authenticated")
    @login_required
    def authenticated_page():
        return "Authenticated page"

    @application.route("/librarian-only")
    @librarian_required
    def librarian_page():
        return "Librarian page"

    @application.route("/student-only")
    @student_required
    def student_page():
        return "Student page"

    @application.route("/shared")
    @student_or_librarian_required
    def shared_page():
        return "Shared page"

    return application


@pytest.fixture
def role_client(role_app):
    return role_app.test_client()


def login_as(
    client,
    user_id,
    role,
):
    with client.session_transaction() as user_session:
        user_session["user_id"] = user_id
        user_session["role"] = role
        user_session["full_name"] = "Test User"


def test_unauthenticated_user_is_redirected_to_login(
    role_client,
):
    response = role_client.get("/authenticated")

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/auth/login"
    )


def test_authenticated_student_can_access_common_page(
    role_client,
):
    login_as(
        role_client,
        "USR001",
        "student",
    )

    response = role_client.get("/authenticated")

    assert response.status_code == 200
    assert b"Authenticated page" in response.data


def test_librarian_can_access_librarian_page(
    role_client,
):
    login_as(
        role_client,
        "USR002",
        "librarian",
    )

    response = role_client.get("/librarian-only")

    assert response.status_code == 200
    assert b"Librarian page" in response.data


def test_student_cannot_access_librarian_page(
    role_client,
):
    login_as(
        role_client,
        "USR001",
        "student",
    )

    response = role_client.get("/librarian-only")

    assert response.status_code == 403
    assert b"Access denied" in response.data


def test_student_can_access_student_page(
    role_client,
):
    login_as(
        role_client,
        "USR001",
        "student",
    )

    response = role_client.get("/student-only")

    assert response.status_code == 200
    assert b"Student page" in response.data


def test_librarian_cannot_access_student_only_page(
    role_client,
):
    login_as(
        role_client,
        "USR002",
        "librarian",
    )

    response = role_client.get("/student-only")

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        "student",
        "librarian",
        "Student",
        "Librarian",
    ],
)
def test_student_and_librarian_can_access_shared_page(
    role_client,
    role,
):
    login_as(
        role_client,
        "USR003",
        role,
    )

    response = role_client.get("/shared")

    assert response.status_code == 200
    assert b"Shared page" in response.data


def test_missing_role_cannot_access_restricted_page(
    role_client,
):
    with role_client.session_transaction() as user_session:
        user_session["user_id"] = "USR004"

    response = role_client.get("/librarian-only")

    assert response.status_code == 403