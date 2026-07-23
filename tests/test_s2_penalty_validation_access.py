import copy

import pytest

from modules.penalty_transaction import routes as penalty_routes


@pytest.fixture(autouse=True)
def reset_demo_penalties():
    original_penalties = copy.deepcopy(penalty_routes.DEMO_PENALTIES)

    penalty_routes.DEMO_PENALTIES["S2P001"] = {
        "penalty_id": "S2P001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "penalty_amount": 10.00,
        "status": "Outstanding"
    }

    penalty_routes.DEMO_PENALTIES["S2P002"] = {
        "penalty_id": "S2P002",
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "penalty_amount": 15.00,
        "status": "Outstanding"
    }

    yield

    penalty_routes.DEMO_PENALTIES.clear()
    penalty_routes.DEMO_PENALTIES.update(original_penalties)


def test_validate_penalty_amount_accepts_positive_amount():
    success, message, amount = penalty_routes.validate_penalty_amount(10)

    assert success is True
    assert amount == 10.00


def test_validate_penalty_amount_rejects_zero_amount():
    success, message, amount = penalty_routes.validate_penalty_amount(0)

    assert success is False
    assert message == "Penalty amount must be greater than zero."
    assert amount is None


def test_validate_penalty_amount_rejects_negative_amount():
    success, message, amount = penalty_routes.validate_penalty_amount(-5)

    assert success is False
    assert message == "Penalty amount must be greater than zero."
    assert amount is None


def test_validate_penalty_amount_rejects_invalid_text():
    success, message, amount = penalty_routes.validate_penalty_amount("abc")

    assert success is False
    assert message == "Invalid penalty amount."
    assert amount is None


def test_student_can_access_own_penalty():
    success, message, penalty = penalty_routes.validate_student_penalty_access(
        "S2P001",
        "S001"
    )

    assert success is True
    assert penalty["student_id"] == "S001"


def test_student_cannot_access_other_student_penalty():
    success, message, penalty = penalty_routes.validate_student_penalty_access(
        "S2P002",
        "S001"
    )

    assert success is False
    assert message == "You are not allowed to access another student's penalty record."


def test_student_can_pay_own_penalty():
    success, message = penalty_routes.pay_student_own_penalty(
        "S2P001",
        "S001",
        10.00,
        "Credit Card"
    )

    assert success is True
    assert message == "Penalty paid successfully."
    assert penalty_routes.DEMO_PENALTIES["S2P001"]["status"] == "Paid"


def test_student_cannot_pay_other_student_penalty():
    success, message = penalty_routes.pay_student_own_penalty(
        "S2P002",
        "S001",
        15.00,
        "Credit Card"
    )

    assert success is False
    assert message == "You are not allowed to access another student's penalty record."
    assert penalty_routes.DEMO_PENALTIES["S2P002"]["status"] == "Outstanding"