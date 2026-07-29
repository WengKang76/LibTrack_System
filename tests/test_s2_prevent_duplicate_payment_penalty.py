import copy

import pytest

from modules.penalty_transaction import routes as penalty_routes


@pytest.fixture(autouse=True)
def reset_demo_data():
    original_penalties = copy.deepcopy(penalty_routes.DEMO_PENALTIES)

    penalty_routes.DEMO_PENALTIES["S2P003"] = {
        "penalty_id": "S2P003",
        "student_id": "S001",
        "transaction_id": "T003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "penalty_amount": 10.00,
        "penalty_type": "Overdue Penalty",
        "status": "Paid"
    }

    penalty_routes.DEMO_PENALTIES["S2P004"] = {
        "penalty_id": "S2P004",
        "student_id": "S001",
        "transaction_id": "T004",
        "book_id": "B004",
        "book_title": "Database System",
        "penalty_amount": 15.00,
        "penalty_type": "Overdue Penalty",
        "status": "Waived"
    }

    penalty_routes.DEMO_PENALTIES["S2P005"] = {
        "penalty_id": "S2P005",
        "student_id": "S001",
        "transaction_id": "T005",
        "book_id": "B005",
        "book_title": "Python Programming",
        "penalty_amount": 20.00,
        "penalty_type": "Overdue Penalty",
        "status": "Outstanding"
    }

    penalty_routes.DEMO_PENALTIES["S2DUP001"] = {
        "penalty_id": "S2DUP001",
        "student_id": "S002",
        "transaction_id": "RTDUP001",
        "book_id": "B006",
        "book_title": "Computer Security",
        "penalty_amount": 25.00,
        "penalty_type": "Rejected Return",
        "status": "Outstanding"
    }

    penalty_routes.DEMO_PENALTIES["S2DUP002"] = {
        "penalty_id": "S2DUP002",
        "student_id": "S003",
        "transaction_id": "OTDUP001",
        "book_id": "B007",
        "book_title": "Artificial Intelligence",
        "penalty_amount": 8.00,
        "penalty_type": "Overdue Penalty",
        "status": "Outstanding"
    }

    yield

    penalty_routes.DEMO_PENALTIES.clear()
    penalty_routes.DEMO_PENALTIES.update(original_penalties)


def test_prevent_payment_for_paid_penalty():
    success, message = penalty_routes.pay_student_own_penalty(
        "S2P003",
        "S001",
        10.00,
        "Credit Card"
    )

    assert success is False
    assert message == "This penalty has already been paid or waived."


def test_prevent_payment_for_waived_penalty():
    success, message = penalty_routes.pay_student_own_penalty(
        "S2P004",
        "S001",
        15.00,
        "Credit Card"
    )

    assert success is False
    assert message == "This penalty has already been paid or waived."


def test_allow_payment_for_outstanding_penalty():
    success, message = penalty_routes.pay_student_own_penalty(
        "S2P005",
        "S001",
        20.00,
        "Credit Card"
    )

    assert success is True
    assert message == "Penalty paid successfully."
    assert penalty_routes.DEMO_PENALTIES["S2P005"]["status"] == "Paid"


def test_detect_duplicate_rejected_return_penalty():
    exists = penalty_routes.penalty_record_exists_for_transaction(
        "RTDUP001",
        "Rejected Return"
    )

    assert exists is True


def test_detect_duplicate_overdue_penalty():
    exists = penalty_routes.penalty_record_exists_for_transaction(
        "OTDUP001",
        "Overdue Penalty"
    )

    assert exists is True


def test_no_duplicate_penalty_for_new_transaction():
    exists = penalty_routes.penalty_record_exists_for_transaction(
        "NEWTRANSACTION001",
        "Rejected Return"
    )

    assert exists is False


def test_penalty_record_exists_for_rejected_return_helper():
    exists = penalty_routes.penalty_record_exists_for_rejected_return(
        "RTDUP001"
    )

    assert exists is True