import copy

import pytest

from modules.penalty_transaction import routes as penalty_routes


@pytest.fixture(autouse=True)
def reset_demo_penalties():
    original_penalties = copy.deepcopy(penalty_routes.DEMO_PENALTIES)

    penalty_routes.DEMO_PENALTIES["S2W001"] = {
        "penalty_id": "S2W001",
        "student_id": "S001",
        "transaction_id": "T001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "penalty_amount": 10.00,
        "penalty_type": "Overdue Penalty",
        "status": "Outstanding"
    }

    penalty_routes.DEMO_PENALTIES["S2W002"] = {
        "penalty_id": "S2W002",
        "student_id": "S002",
        "transaction_id": "T002",
        "book_id": "B002",
        "book_title": "Database System",
        "penalty_amount": 15.00,
        "penalty_type": "Overdue Penalty",
        "status": "Paid"
    }

    penalty_routes.DEMO_PENALTIES["S2W003"] = {
        "penalty_id": "S2W003",
        "student_id": "S003",
        "transaction_id": "T003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "penalty_amount": 20.00,
        "penalty_type": "Overdue Penalty",
        "status": "Waived"
    }

    yield

    penalty_routes.DEMO_PENALTIES.clear()
    penalty_routes.DEMO_PENALTIES.update(original_penalties)


def test_validate_waiver_reason_accepts_valid_reason():
    success, message, reason = penalty_routes.validate_waiver_reason(
        "Valid medical reason"
    )

    assert success is True
    assert reason == "Valid medical reason"


def test_validate_waiver_reason_rejects_empty_reason():
    success, message, reason = penalty_routes.validate_waiver_reason("")

    assert success is False
    assert message == "Waiver reason is required."


def test_validate_waiver_reason_rejects_short_reason():
    success, message, reason = penalty_routes.validate_waiver_reason("abc")

    assert success is False
    assert message == "Waiver reason must be at least 5 characters."


def test_waive_outstanding_penalty_successfully():
    success, message = penalty_routes.waive_penalty(
        "S2W001",
        "Student provided valid reason",
        "Librarian"
    )

    assert success is True
    assert message == "Penalty waived successfully."
    assert penalty_routes.DEMO_PENALTIES["S2W001"]["status"] == "Waived"
    assert penalty_routes.DEMO_PENALTIES["S2W001"]["waiver_reason"] == "Student provided valid reason"


def test_paid_penalty_cannot_be_waived():
    success, message = penalty_routes.waive_penalty(
        "S2W002",
        "Valid reason",
        "Librarian"
    )

    assert success is False
    assert message == "Paid penalties cannot be waived."


def test_already_waived_penalty_cannot_be_waived_again():
    success, message = penalty_routes.waive_penalty(
        "S2W003",
        "Valid reason",
        "Librarian"
    )

    assert success is False
    assert message == "Penalty has already been waived."


def test_audit_details_are_recorded_after_waiver():
    success, message = penalty_routes.waive_penalty(
        "S2W001",
        "Student provided valid reason",
        "Librarian"
    )

    penalty = penalty_routes.DEMO_PENALTIES["S2W001"]

    assert success is True
    assert penalty["waived_by"] == "Librarian"
    assert "waived_date" in penalty
    assert penalty["last_action"] == "Waive Penalty"
    assert penalty["updated_by"] == "Librarian"
    assert "updated_at" in penalty