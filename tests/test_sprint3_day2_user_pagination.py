import pytest

import modules.user_management.routes as user_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


class FakeDocumentSnapshot:
    def __init__(
        self,
        document_id,
        data,
    ):
        self.id = document_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeUsersCollection:
    def __init__(self, users):
        self.users = users

    def stream(self):
        return [
            FakeDocumentSnapshot(
                document_id,
                user,
            )
            for document_id, user
            in self.users.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.users = {}

        for number in range(1, 24):
            document_id = f"USR{number:03d}"

            self.users[document_id] = {
                "user_id": document_id,
                "student_id": (
                    f"24WMR{number:05d}"
                ),
                "full_name": (
                    f"Student {number:02d}"
                ),
                "email": (
                    f"student{number:02d}"
                    "@student.tarc.edu.my"
                ),
                "role": "Student",
                "account_status": (
                    "Active"
                    if number % 2 == 1
                    else "Inactive"
                ),
                "created_at": (
                    "2026-08-01 09:00:00"
                ),
            }

        self.users["LIB001"] = {
            "user_id": "LIB001",
            "full_name": "Library Administrator",
            "email": "admin@tarumt.edu.my",
            "role": "Librarian",
            "account_status": "Active",
        }

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(
            self.users
        )


@pytest.fixture
def pagination_database(
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        user_routes,
        "db",
        fake_database,
    )

    return fake_database


def _page_text(response):
    return response.data.decode(
        "utf-8"
    )


# ============================================================
# SCRUM-1522: PAGINATE STUDENT MANAGEMENT LIST
# ============================================================

def test_scrum_1522_first_page_displays_ten_students(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=1"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Student 01" in page_text
    assert "Student 10" in page_text
    assert "Student 11" not in page_text
    assert "Showing" in page_text
    assert "23" in page_text


def test_scrum_1522_second_page_displays_next_ten_students(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=2"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Student 11" in page_text
    assert "Student 20" in page_text
    assert "Student 10" not in page_text
    assert "Student 21" not in page_text


def test_scrum_1522_final_page_displays_remaining_students(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=3"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Student 21" in page_text
    assert "Student 22" in page_text
    assert "Student 23" in page_text
    assert "Student 20" not in page_text


def test_scrum_1522_invalid_page_defaults_to_first_page(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=invalid"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Student 01" in page_text
    assert "Student 10" in page_text
    assert "Student 11" not in page_text


def test_scrum_1522_page_above_range_uses_last_page(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=999"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Student 21" in page_text
    assert "Student 23" in page_text
    assert "Student 20" not in page_text


def test_scrum_1522_pagination_preserves_filter_and_sort(
    client,
    pagination_database,
):
    response = client.get(
        (
            "/users/"
            "?status=active"
            "&sort=name_desc"
            "&page=1"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "status=active"
        in page_text
    )

    assert (
        "sort=name_desc"
        in page_text
    )

    assert (
        "page=2"
        in page_text
    )


def test_scrum_1522_does_not_paginate_librarian_accounts(
    client,
    pagination_database,
):
    response = client.get(
        "/users/?page=1"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Library Administrator"
        not in page_text
    )

    assert (
        "admin@tarumt.edu.my"
        not in page_text
    )