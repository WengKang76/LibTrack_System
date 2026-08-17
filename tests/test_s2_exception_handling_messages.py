import copy

import pytest

from modules.penalty_transaction import routes as penalty_routes


@pytest.fixture(autouse=True)
def reset_demo_data(monkeypatch):
    original_penalties = copy.deepcopy(
        penalty_routes.DEMO_PENALTIES
    )

    # This test suite specifically tests the demo/test fallback.
    monkeypatch.setattr(penalty_routes, "db", None)

    fake_transactions = {
        "RT1084": {
            "transaction_id": "RT1084",
            "student_id": "S001",
            "book_id": "B001",
            "book_title": "Python Programming",
            "status": "Rejected",
        },
        "RT1084_PENDING": {
            "transaction_id": "RT1084_PENDING",
            "student_id": "S001",
            "book_id": "B002",
            "book_title": "Database System",
            "status": "Pending",
        },
        "RT1084_DUP": {
            "transaction_id": "RT1084_DUP",
            "student_id": "S001",
            "book_id": "B004",
            "book_title": "Computer Security",
            "status": "Rejected",
        },
        "RT1085": {
            "transaction_id": "RT1085",
            "student_id": "S002",
            "book_id": "B003",
            "book_title": "Software Engineering",
            "status": "Returned",
        },
        "RT1085_DUP": {
            "transaction_id": "RT1085_DUP",
            "student_id": "S002",
            "book_id": "B005",
            "book_title": "Artificial Intelligence",
            "status": "Returned",
        },
    }

    def fake_get_return_transaction_by_id(transaction_id):
        transaction = fake_transactions.get(transaction_id)

        if transaction is None:
            return None

        return transaction.copy()

    monkeypatch.setattr(
        penalty_routes,
        "get_return_transaction_by_id",
        fake_get_return_transaction_by_id,
    )

    penalty_routes.DEMO_PENALTIES["DUP1084"] = {
        "penalty_id": "DUP1084",
        "student_id": "S001",
        "transaction_id": "RT1084_DUP",
        "book_id": "B004",
        "book_title": "Computer Security",
        "penalty_type": "Rejected Return",
        "penalty_amount": 10.00,
        "status": "Outstanding",
    }

    penalty_routes.DEMO_PENALTIES["DUP1085"] = {
        "penalty_id": "DUP1085",
        "student_id": "S002",
        "transaction_id": "RT1085_DUP",
        "book_id": "B005",
        "book_title": "Artificial Intelligence",
        "penalty_type": "Lost/Damaged Book",
        "penalty_amount": 50.00,
        "status": "Outstanding",
    }

    yield

    penalty_routes.DEMO_PENALTIES.clear()
    penalty_routes.DEMO_PENALTIES.update(original_penalties)


def test_clear_action_message_for_failed_action():
    message = penalty_routes.create_penalty_action_message(
        "Penalty payment", False, "Penalty amount must be greater than zero."
    )

    assert (
        message
        == "Penalty payment failed. Reason: Penalty amount must be greater than zero."
    )


def test_clear_action_message_for_successful_action():
    message = penalty_routes.create_penalty_action_message(
        "Penalty waiver", True, "Penalty waived successfully."
    )

    assert (
        message == "Penalty waiver completed successfully. Penalty waived successfully."
    )


def test_rejected_return_exception_creates_penalty_record():
    success, message = penalty_routes.handle_rejected_return_exception(
        "RT1084", 25.00, "Book condition was not acceptable", "Librarian"
    )

    assert success is True
    assert "completed successfully" in message


def test_rejected_return_exception_blocks_pending_return():
    success, message = penalty_routes.handle_rejected_return_exception(
        "RT1084_PENDING", 25.00, "Book condition was not acceptable", "Librarian"
    )

    assert success is False
    assert "failed. Reason:" in message
    assert "Penalty can only be created after the return is rejected." in message


def test_rejected_return_exception_blocks_duplicate_penalty():
    success, message = penalty_routes.handle_rejected_return_exception(
        "RT1084_DUP", 25.00, "Duplicate rejected return penalty", "Librarian"
    )

    assert success is False
    assert "Penalty record already exists for this rejected return." in message


def test_lost_book_exception_creates_penalty_record():
    success, message = penalty_routes.create_lost_damaged_book_exception_penalty(
        "RT1085", "Lost", "Student reported that the book was lost", 80.00, "Librarian"
    )

    assert success is True
    assert "completed successfully" in message

    created_records = [
        penalty
        for penalty in penalty_routes.DEMO_PENALTIES.values()
        if penalty.get("transaction_id") == "RT1085"
        and penalty.get("penalty_type") == "Lost/Damaged Book"
    ]

    assert len(created_records) == 1
    assert created_records[0]["exception_type"] == "Lost"


def test_damaged_book_exception_creates_penalty_record():
    success, message = penalty_routes.create_lost_damaged_book_exception_penalty(
        "RT1085", "Damaged", "Book cover and pages were damaged", 40.00, "Librarian"
    )

    assert success is True
    assert "completed successfully" in message


def test_lost_damaged_exception_rejects_invalid_exception_type():
    success, message = penalty_routes.create_lost_damaged_book_exception_penalty(
        "RT1085", "Missing", "Invalid exception type", 40.00, "Librarian"
    )

    assert success is False
    assert "Book exception type must be Lost or Damaged." in message


def test_lost_damaged_exception_rejects_duplicate_penalty():
    fake_transaction = {
        "transaction_id": "RT1085_DUP",
        "student_id": "S002",
        "book_id": "B005",
        "book_title": "Artificial Intelligence",
        "status": "Returned",
    }

    success, message = penalty_routes.create_lost_damaged_book_exception_penalty(
        fake_transaction["transaction_id"],
        "Lost",
        "Duplicate lost book exception",
        80.00,
        "Librarian",
    )

    assert success is False
    assert (
        "Penalty record already exists for this lost or damaged book exception."
        in message
    )
