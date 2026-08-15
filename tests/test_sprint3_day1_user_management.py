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
        self.users = {
            "USR201": {
                "user_id": "USR201",
                "student_id": "24WMR00001",
                "full_name": "Zara Lim",
                "email": (
                    "zara.lim@student.tarc.edu.my"
                ),
                "role": "Student",
                "account_status": "Active",
                "created_at": (
                    "2026-08-01 09:00:00"
                ),
            },
            "USR202": {
                "user_id": "USR202",
                "student_id": "24WMR00002",
                "full_name": "Aaron Tan",
                "email": (
                    "aaron.tan@student.tarc.edu.my"
                ),
                "role": "Student",
                "account_status": "Inactive",
                "created_at": (
                    "2026-08-03 09:00:00"
                ),
            },
            "USR203": {
                "user_id": "USR203",
                "student_id": "24WMR00003",
                "full_name": "Mei Ling Wong",
                "email": (
                    "mei.wong@student.tarc.edu.my"
                ),
                "role": "Student",
                "account_status": "Active",
                "created_at": (
                    "2026-08-02 09:00:00"
                ),
            },
            "LIB001": {
                "user_id": "LIB001",
                "full_name": (
                    "Library Administrator"
                ),
                "email": "admin@tarumt.edu.my",
                "role": "Librarian",
                "account_status": "Active",
                "created_at": (
                    "2026-07-01 09:00:00"
                ),
            },
        }

    def collection(self, collection_name):
        assert collection_name == "users"

        return FakeUsersCollection(
            self.users
        )


@pytest.fixture
def sprint3_user_database(
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        user_routes,
        "db",
        fake_database,
    )

    return fake_database


# ============================================================
# SCRUM-1519: SEARCH REGISTERED STUDENTS
# ============================================================

def test_scrum_1519_searches_by_partial_name_case_insensitively(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=MEI"
    )

    assert response.status_code == 200
    assert b"Mei Ling Wong" in response.data
    assert b"Zara Lim" not in response.data
    assert b"Aaron Tan" not in response.data


def test_scrum_1519_searches_by_student_id(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=24wmr00002"
    )

    assert response.status_code == 200
    assert b"Aaron Tan" in response.data
    assert b"Zara Lim" not in response.data


def test_scrum_1519_searches_by_email(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=zara.lim"
    )

    assert response.status_code == 200
    assert b"Zara Lim" in response.data
    assert b"Aaron Tan" not in response.data


def test_scrum_1519_unknown_search_displays_clear_message(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=not-a-student"
    )

    assert response.status_code == 200

    assert (
        b"No Student accounts found"
        in response.data
    )

    assert (
        b"Clear Search and Filters"
        in response.data
    )


def test_scrum_1519_search_never_displays_librarian_accounts(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=admin"
    )

    assert response.status_code == 200

    assert (
        b"Library Administrator"
        not in response.data
    )

    assert (
        b"admin@tarumt.edu.my"
        not in response.data
    )


# ============================================================
# SCRUM-1520: FILTER STUDENT ACCOUNTS BY STATUS
# ============================================================

def test_scrum_1520_filters_active_students(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?status=active"
    )

    assert response.status_code == 200
    assert b"Zara Lim" in response.data
    assert b"Mei Ling Wong" in response.data
    assert b"Aaron Tan" not in response.data


def test_scrum_1520_filters_inactive_students(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?status=inactive"
    )

    assert response.status_code == 200
    assert b"Aaron Tan" in response.data
    assert b"Zara Lim" not in response.data
    assert b"Mei Ling Wong" not in response.data


def test_scrum_1520_filter_works_with_search(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?q=tan&status=inactive"
    )

    assert response.status_code == 200
    assert b"Aaron Tan" in response.data
    assert b"Zara Lim" not in response.data


def test_scrum_1520_invalid_status_is_handled_safely(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?status=unknown"
    )

    assert response.status_code == 200
    assert b"Zara Lim" in response.data
    assert b"Aaron Tan" in response.data
    assert b"Mei Ling Wong" in response.data


# ============================================================
# SCRUM-1521: SORT STUDENT ACCOUNTS
# ============================================================

def _page_text(response):
    return response.data.decode(
        "utf-8"
    )


def test_scrum_1521_sorts_names_descending(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?sort=name_desc"
    )

    page_text = _page_text(response)

    assert (
        page_text.index("Zara Lim")
        < page_text.index("Mei Ling Wong")
        < page_text.index("Aaron Tan")
    )


def test_scrum_1521_sorts_student_ids_ascending(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?sort=student_id_asc"
    )

    page_text = _page_text(response)

    assert (
        page_text.index("24WMR00001")
        < page_text.index("24WMR00002")
        < page_text.index("24WMR00003")
    )


def test_scrum_1521_sorts_newest_registration_first(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?sort=registration_newest"
    )

    page_text = _page_text(response)

    assert (
        page_text.index("Aaron Tan")
        < page_text.index("Mei Ling Wong")
        < page_text.index("Zara Lim")
    )


def test_scrum_1521_sorts_active_status_first(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?sort=status_active_first"
    )

    page_text = _page_text(response)

    assert (
        page_text.index("Aaron Tan")
        > page_text.index("Zara Lim")
    )

    assert (
        page_text.index("Aaron Tan")
        > page_text.index("Mei Ling Wong")
    )


def test_scrum_1521_sort_works_with_search_and_filter(
    client,
    sprint3_user_database,
):
    response = client.get(
        (
            "/users/?q=zara"
            "&status=active"
            "&sort=name_desc"
        )
    )

    page_text = _page_text(response)

    assert "Zara Lim" in page_text
    assert "Aaron Tan" not in page_text
    assert "Mei Ling Wong" not in page_text

    assert (
        'value="zara"'
        in page_text
    )

    assert (
        'value="active"'
        in page_text
    )

    assert (
        'value="name_desc"'
        in page_text
    )


def test_scrum_1521_invalid_sort_defaults_to_name_ascending(
    client,
    sprint3_user_database,
):
    response = client.get(
        "/users/?sort=invalid-sort"
    )

    page_text = _page_text(response)

    assert (
        page_text.index("Aaron Tan")
        < page_text.index("Mei Ling Wong")
        < page_text.index("Zara Lim")
    )