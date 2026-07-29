# SCRUM-1188: Prevent duplicate active reservations

import pytest

from modules.catalogue_reservation import routes as catalogue_routes


def _unavailable_book():
    return {
        "book_id": "B001",
        "title": "Secure Software Design",
        "status": "Unavailable",
        "available_copies": 0,
    }


def _reservation(status, student_id="S001"):
    return {
        "reservation_id": "R001",
        "student_id": student_id,
        "book_id": "B001",
        "book_title": "Secure Software Design",
        "reservation_date": "2026-07-24 09:00:00",
        "status": status,
    }


@pytest.mark.parametrize(
    "active_status",
    ["Active", "Pending", "Approved", "Ready_for_Collection"],
)
def test_all_active_reservation_statuses_block_duplicate(
    app_factory,
    active_status,
):
    app = app_factory(
        books=[_unavailable_book()],
        reservations=[_reservation(active_status)],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    stored = app.extensions["fake_firestore"].collections["reservations"]

    assert response.status_code == 200
    assert "already have an active reservation" in response.get_data(
        as_text=True
    )
    assert len(stored) == 1


@pytest.mark.parametrize("inactive_status", ["Cancelled", "Expired"])
def test_inactive_reservation_status_allows_new_reservation(
    app_factory,
    inactive_status,
):
    app = app_factory(
        books=[_unavailable_book()],
        reservations=[_reservation(inactive_status)],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    stored = app.extensions["fake_firestore"].collections["reservations"]

    assert response.status_code == 200
    assert len(stored) == 2
    assert stored[-1]["status"] == "Active"


def test_other_students_active_reservation_does_not_block_current_student(
    app_factory,
):
    app = app_factory(
        books=[_unavailable_book()],
        reservations=[_reservation("Active", student_id="S999")],
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    stored = app.extensions["fake_firestore"].collections["reservations"]

    assert response.status_code == 200
    assert len(stored) == 2
    assert stored[-1]["student_id"] == "S001"


def test_duplicate_is_checked_again_immediately_before_insert(
    app_factory,
    monkeypatch,
):
    app = app_factory(books=[_unavailable_book()])
    client = app.test_client()
    duplicate_results = iter([False, True])

    monkeypatch.setattr(
        catalogue_routes,
        "_student_has_active_reservation",
        lambda _student_id, _book_id: next(duplicate_results),
    )

    response = client.post(
        "/catalogue/reserve/B001",
        follow_redirects=True,
    )
    stored = app.extensions["fake_firestore"].collections["reservations"]

    assert response.status_code == 200
    assert "already have an active reservation" in response.get_data(
        as_text=True
    )
    assert stored == []
