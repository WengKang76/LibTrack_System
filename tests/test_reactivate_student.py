"""Additional tests for student account reactivation.

This is a new test file. It does not replace
tests/test_user_management.py.
"""

import pytest
from datetime import datetime

from tests.test_user_management import (
    use_fake_database,
)


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)

def test_inactive_student_shows_reactivate_button(client, monkeypatch):
    use_fake_database(monkeypatch)

    response = client.get("/users/details/USR003")

    assert response.status_code == 200
    assert b"Reactivate Student Account" in response.data
    assert b"Deactivate Student Account" not in response.data


def test_reactivates_inactive_student(client, monkeypatch):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/reactivate/USR003")

    assert response.status_code == 302
    updated_user = fake_database.users["USR003"]
    assert updated_user["account_status"] == "Active"
    assert "reactivated_at" in updated_user
    assert "updated_at" in updated_user
    datetime.strptime(
        updated_user["reactivated_at"],
        "%Y-%m-%d %H:%M:%S",
    )


def test_reactivation_updates_only_selected_student(client, monkeypatch):
    fake_database = use_fake_database(monkeypatch)
    other_user_before = dict(fake_database.users["USR001"])

    client.post("/users/reactivate/USR003")

    assert fake_database.users["USR003"]["account_status"] == "Active"
    assert fake_database.users["USR001"] == other_user_before


def test_reactivation_rejects_already_active_student(client, monkeypatch):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/reactivate/USR001")

    assert response.status_code == 400
    assert b"This Student account is already active." in response.data
    assert fake_database.update_history == []


def test_reactivation_rejects_librarian(client, monkeypatch):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/reactivate/USR005")

    assert response.status_code == 400
    assert b"Only Student accounts can be reactivated." in response.data
    assert fake_database.update_history == []


def test_reactivation_unknown_user_returns_404(client, monkeypatch):
    fake_database = use_fake_database(monkeypatch)

    response = client.post("/users/reactivate/UNKNOWN")

    assert response.status_code == 404
    assert b"User record not found." in response.data
    assert fake_database.update_history == []


def test_student_account_can_be_deactivated_and_reactivated(
    client,
    monkeypatch,
):
    fake_database = use_fake_database(
        monkeypatch
    )

    # Active -> Inactive
    deactivate_response = client.post(
        "/users/deactivate/USR001"
    )

    assert deactivate_response.status_code == 302

    assert (
        fake_database.users["USR001"][
            "account_status"
        ]
        == "Inactive"
    )

    # Inactive -> Active
    reactivate_response = client.post(
        "/users/reactivate/USR001"
    )

    assert reactivate_response.status_code == 302

    assert (
        fake_database.users["USR001"][
            "account_status"
        ]
        == "Active"
    )

    # Two Firestore update operations were recorded.
    assert len(
        fake_database.update_history
    ) == 2

    assert (
        fake_database.update_history[0][
            "updated_data"
        ]["account_status"]
        == "Inactive"
    )

    assert (
        fake_database.update_history[1][
            "updated_data"
        ]["account_status"]
        == "Active"
    )
