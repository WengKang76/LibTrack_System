import pytest
from werkzeug.security import check_password_hash

import modules.authentication.routes as authentication_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None

        return dict(self._data)


class FakeDocumentReference:
    def __init__(self, database, document_id):
        self.database = database
        self.document_id = document_id

    def set(self, data):
        self.database.users[
            self.document_id
        ] = dict(data)


class FakeUsersCollection:
    def __init__(self, database):
        self.database = database

    def stream(self):
        return [
            FakeDocumentSnapshot(
                document_id,
                data,
            )
            for document_id, data
            in self.database.users.items()
        ]

    def document(self, document_id):
        return FakeDocumentReference(
            self.database,
            document_id,
        )


class FakeDatabase:
    def __init__(self):
        self.users = {
            "USR001": {
                "user_id": "USR001",
                "student_id": "24WMR00001",
                "full_name": "Existing Student",
                "email": "existing@student.demo",
                "phone_number": "012-3456789",
                "password_hash": "existing-hash",
                "role": "Student",
                "account_status": "Active",
            }
        }

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(self)


@pytest.fixture
def registration_database(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        authentication_routes,
        "db",
        fake_database,
    )

    return fake_database


def valid_registration_data():
    return {
        "student_id": "24WMR00002",
        "full_name": "Sherman Tan",
        "email": "sherman@student.demo",
        "phone_number": "012-9876543",
        "password": "Secure@123",
        "confirm_password": "Secure@123",
    }


def test_registration_page_loads(
    client,
    registration_database,
):
    response = client.get(
        "/auth/register"
    )

    assert response.status_code == 200
    assert b"Student Registration" in response.data
    assert b"Register Student Account" in response.data


def test_valid_student_registration_creates_account(
    client,
    registration_database,
):
    response = client.post(
        "/auth/register",
        data=valid_registration_data(),
    )

    assert response.status_code == 302

    created_user = registration_database.users[
        "USR002"
    ]

    assert created_user["student_id"] == "24WMR00002"
    assert created_user["full_name"] == "Sherman Tan"
    assert created_user["email"] == "sherman@student.demo"
    assert created_user["role"] == "Student"
    assert created_user["account_status"] == "Inactive"
    assert created_user["is_dummy_account"] is False


def test_password_is_hashed_before_storage(
    client,
    registration_database,
):
    client.post(
        "/auth/register",
        data=valid_registration_data(),
    )

    created_user = registration_database.users[
        "USR002"
    ]

    assert "password" not in created_user
    assert "confirm_password" not in created_user

    assert created_user["password_hash"] != "Secure@123"

    assert check_password_hash(
        created_user["password_hash"],
        "Secure@123",
    )


def test_required_registration_fields_are_validated(
    client,
    registration_database,
):
    response = client.post(
        "/auth/register",
        data={},
    )

    assert response.status_code == 400
    assert b"Student ID is required." in response.data
    assert b"Full name is required." in response.data
    assert b"Email address is required." in response.data
    assert b"Phone number is required." in response.data
    assert b"Password is required." in response.data

    assert len(
        registration_database.users
    ) == 1


@pytest.mark.parametrize(
    "password",
    [
        "Short1!",
        "lowercase1!",
        "UPPERCASE1!",
        "NoNumber!",
        "NoSpecial123",
        "Space Password1!",
    ],
)
def test_weak_password_is_rejected(
    client,
    registration_database,
    password,
):
    form_data = valid_registration_data()
    form_data["password"] = password
    form_data["confirm_password"] = password

    response = client.post(
        "/auth/register",
        data=form_data,
    )

    assert response.status_code == 400
    assert b"Password must" in response.data

    assert "USR002" not in registration_database.users


def test_password_confirmation_must_match(
    client,
    registration_database,
):
    form_data = valid_registration_data()

    form_data["confirm_password"] = (
        "Different@123"
    )

    response = client.post(
        "/auth/register",
        data=form_data,
    )

    assert response.status_code == 400

    assert (
        b"Password and confirmation password "
        b"do not match."
        in response.data
    )

    assert "USR002" not in registration_database.users


def test_duplicate_email_is_rejected_case_insensitively(
    client,
    registration_database,
):
    form_data = valid_registration_data()

    form_data["email"] = (
        "EXISTING@STUDENT.DEMO"
    )

    response = client.post(
        "/auth/register",
        data=form_data,
    )

    assert response.status_code == 400

    assert (
        b"An account already exists with "
        b"this email address."
        in response.data
    )

    assert "USR002" not in registration_database.users


def test_duplicate_student_id_is_rejected(
    client,
    registration_database,
):
    form_data = valid_registration_data()
    form_data["student_id"] = "24wmr00001"

    response = client.post(
        "/auth/register",
        data=form_data,
    )

    assert response.status_code == 400

    assert (
        b"An account already exists with "
        b"this student ID."
        in response.data
    )


def test_registration_assigns_student_role_automatically(
    client,
    registration_database,
):
    form_data = valid_registration_data()
    form_data["role"] = "Librarian"

    client.post(
        "/auth/register",
        data=form_data,
    )

    created_user = registration_database.users[
        "USR002"
    ]

    assert created_user["role"] == "Student"


def test_registration_page_has_show_password_control(
    client,
    registration_database,
):
    response = client.get(
        "/auth/register"
    )

    assert response.status_code == 200
    assert b'id="show_passwords"' in response.data
    assert b'class="password-input"' in response.data
    assert b"Show passwords" in response.data