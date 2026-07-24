from datetime import datetime


import modules.user_management.routes as user_routes


class FakeDocumentSnapshot:
    def __init__(self, document_id, data):
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        if self._data is None:
            return None

        return dict(self._data)


class FakeUserDocumentReference:
    def __init__(self, database, user_id):
        self.database = database
        self.user_id = user_id
        self.id = user_id

    def get(self):
        user_data = self.database.users.get(self.user_id)

        return FakeDocumentSnapshot(
            self.user_id,
            user_data,
        )

    def update(self, updated_data):
        if self.user_id not in self.database.users:
            raise KeyError(f"Unknown user ID: {self.user_id}")

        self.database.users[self.user_id].update(dict(updated_data))

        self.database.update_history.append(
            {
                "user_id": self.user_id,
                "updated_data": dict(updated_data),
            }
        )


class FakeUsersCollection:
    def __init__(self, database):
        self.database = database

    def document(self, user_id):
        return FakeUserDocumentReference(
            self.database,
            user_id,
        )

    def stream(self):
        return [
            FakeDocumentSnapshot(user_id, data)
            for user_id, data in self.database.users.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.users = {
            "USR001": {
                "user_id": "USR001",
                "full_name": "Alicia Tan",
                "email": ("alicia.tan@student.demo"),
                "phone_number": "012-3456789",
                "role": "Student",
                "account_status": "Active",
                "created_at": ("2026-07-16 10:00:00"),
                "updated_at": ("2026-07-16 10:00:00"),
                "is_dummy_account": True,
            },
            "USR002": {
                "user_id": "USR002",
                "full_name": "Daniel Lee",
                "email": ("daniel.lee@student.demo"),
                "phone_number": "013-4567890",
                "role": "Student",
                "account_status": "Active",
                "created_at": ("2026-07-16 10:00:00"),
                "updated_at": ("2026-07-16 10:00:00"),
                "is_dummy_account": True,
            },
            "USR003": {
                "user_id": "USR003",
                "full_name": "Nur Aisyah",
                "email": ("nur.aisyah@student.demo"),
                "phone_number": "014-5678901",
                "role": "Student",
                "account_status": "Inactive",
                "created_at": ("2026-07-16 10:00:00"),
                "updated_at": ("2026-07-16 10:00:00"),
                "is_dummy_account": True,
            },
            "USR005": {
                "user_id": "USR005",
                "full_name": "Sarah Wong",
                "email": ("sarah.wong@staff.demo"),
                "phone_number": "017-7890123",
                "role": "Librarian",
                "account_status": "Active",
                "created_at": ("2026-07-16 10:00:00"),
                "updated_at": ("2026-07-16 10:00:00"),
                "is_dummy_account": True,
            },
        }

        self.update_history = []

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(self)


def use_fake_database(monkeypatch):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        user_routes,
        "db",
        fake_database,
    )

    return fake_database


# ============================================================
# SCRUM-511: VIEW ALL USERS
# ============================================================


def test_scrum_511_manage_users_page_loads(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/")

    assert response.status_code == 200
    assert b"User Management" in response.data
    assert b"Demonstration data" in response.data


def test_scrum_511_displays_all_dummy_users(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/")

    assert response.status_code == 200

    expected_users = [
        b"USR001",
        b"Alicia Tan",
        b"USR002",
        b"Daniel Lee",
        b"USR003",
        b"Nur Aisyah",
        b"USR005",
        b"Sarah Wong",
    ]

    for expected_value in expected_users:
        assert expected_value in response.data


def test_scrum_511_displays_roles_and_statuses(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/")

    assert response.status_code == 200
    assert b"Student" in response.data
    assert b"Librarian" in response.data
    assert b"Active" in response.data
    assert b"Inactive" in response.data


def test_scrum_511_sorts_users_by_full_name(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/")

    page_text = response.data.decode("utf-8")

    assert page_text.index("Alicia Tan") < page_text.index("Daniel Lee")

    assert page_text.index("Daniel Lee") < page_text.index("Nur Aisyah")

    assert page_text.index("Nur Aisyah") < page_text.index("Sarah Wong")


def test_scrum_511_empty_database_displays_message(
    client,
    monkeypatch,
):
    fake_database = FakeDatabase()
    fake_database.users = {}

    monkeypatch.setattr(
        user_routes,
        "db",
        fake_database,
    )

    response = client.get("/users/")

    assert response.status_code == 200
    assert b"No user records found" in response.data


# ============================================================
# SCRUM-512: VIEW SELECTED USER DETAILS
# ============================================================


def test_scrum_512_student_details_page_loads(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/USR001")

    assert response.status_code == 200
    assert b"User Details" in response.data
    assert b"USR001" in response.data
    assert b"Alicia Tan" in response.data
    assert b"alicia.tan@student.demo" in response.data
    assert b"012-3456789" in response.data
    assert b"Student" in response.data
    assert b"Active" in response.data


def test_scrum_512_active_student_shows_deactivate_button(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/USR001")

    assert response.status_code == 200

    assert b"Deactivate Student Account" in response.data


def test_scrum_512_inactive_student_shows_inactive_message(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/USR003")

    assert response.status_code == 200

    assert b"This Student account is currently inactive." in response.data

    assert b"Deactivate Student Account" not in response.data


def test_scrum_512_librarian_is_protected(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/USR005")

    assert response.status_code == 200

    assert b"Librarian accounts cannot be deactivated" in response.data

    assert b"Deactivate Student Account" not in response.data


def test_scrum_512_unknown_user_returns_404(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/UNKNOWN")

    assert response.status_code == 404
    assert b"User record not found." in response.data


# ============================================================
# SCRUM-509: DEACTIVATE STUDENT ACCOUNT
# ============================================================


def test_scrum_509_deactivates_active_student(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/deactivate/USR001")

    assert response.status_code == 302

    updated_user = fake_database.users["USR001"]

    assert updated_user["account_status"] == "Inactive"

    assert "deactivated_at" in updated_user
    assert "updated_at" in updated_user

    datetime.strptime(
        updated_user["deactivated_at"],
        "%Y-%m-%d %H:%M:%S",
    )


def test_scrum_509_updates_only_selected_student(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    second_user_before = dict(fake_database.users["USR002"])

    client.post("/users/deactivate/USR001")

    assert fake_database.users["USR001"]["account_status"] == "Inactive"

    assert fake_database.users["USR002"] == second_user_before


def test_scrum_509_records_one_database_update(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    client.post("/users/deactivate/USR001")

    assert len(fake_database.update_history) == 1

    update_record = fake_database.update_history[0]

    assert update_record["user_id"] == "USR001"

    assert update_record["updated_data"]["account_status"] == "Inactive"


def test_scrum_509_redirects_to_selected_user_details(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post("/users/deactivate/USR001")

    assert response.status_code == 302

    assert response.headers["Location"].endswith("/users/details/USR001")


def test_scrum_509_displays_success_message(
    client,
    monkeypatch,
):
    use_fake_database(monkeypatch)

    response = client.post(
        "/users/deactivate/USR001",
        follow_redirects=True,
    )

    assert response.status_code == 200

    assert b"Alicia Tan account was " b"deactivated successfully." in response.data


def test_scrum_509_rejects_already_inactive_student(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/deactivate/USR003")

    assert response.status_code == 400

    assert b"This Student account is already inactive." in response.data

    assert fake_database.update_history == []


def test_scrum_509_rejects_librarian_account(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/deactivate/USR005")

    assert response.status_code == 400

    assert b"Only Student accounts can be deactivated." in response.data

    assert fake_database.users["USR005"]["account_status"] == "Active"

    assert fake_database.update_history == []


def test_scrum_509_unknown_user_returns_404(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/deactivate/UNKNOWN")

    assert response.status_code == 404
    assert b"User record not found." in response.data
    assert fake_database.update_history == []
