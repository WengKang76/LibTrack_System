"""Tests for borrowing service functions."""

import pytest

from modules.borrowing.repository import (
    borrow_requests,
    borrow_transactions,
    find_request,
    find_borrow_transaction,
    get_borrow_transactions,
)

from modules.borrowing.services import (
    approve_borrow_request,
    request_book_return,
)


@pytest.fixture(autouse=True)
def reset_borrow_requests():
    """Reset borrow request repository before each test."""
    borrow_requests.clear()
    borrow_transactions.clear()

    borrow_requests.extend(
        [
            {
                "id": 1,
                "student": "Alice",
                "book": "Database System Concepts",
                "status": "Pending",
            },
            {
                "id": 2,
                "student": "John",
                "book": "Software Engineering",
                "status": "Pending",
            },
        ]
    )


# ==================================================
# User Story 1:
# As a librarian, I want to approve a borrowing request
# so that the book can be officially issued to student.
# ==================================================


def test_approve_pending_borrow_request():
    """
    GIVEN a borrow request exists with status "Pending"
    WHEN the librarian approves the borrowing request
    THEN the approval process should succeed and updated to "Approved"
    """
    result = approve_borrow_request(1)

    assert result is True

    request = find_request(1)

    assert request is not None
    assert request["status"] == "Approved"


def test_approve_non_existing_request():
    """
    GIVEN a borrow request ID that does not exist in the system
    WHEN the librarian attempts to approve the invalid request
    THEN the system should reject the approval attempt
    """
    result = approve_borrow_request(999)

    assert result is False


def test_cannot_approve_already_approved_request():
    """
    GIVEN a borrow request has already been approved
    WHEN the librarian attempts to approve the same request again
    THEN the system should prevent duplicate approval
    """
    approve_borrow_request(1)

    result = approve_borrow_request(1)

    assert result is False


# ==================================================
# User Story 2:
# As a librarian, I want the system to automatically
# generate a due date when a borrowing request is approved
# so that all borrowing periods follow library policy.
# ==================================================


def test_approval_creates_borrow_transaction():
    """
    GIVEN a pending borrowing request exists
    WHEN the librarian approves the borrowing request
    THEN the system should create a borrow transaction
    """
    approve_borrow_request(1)

    transactions = get_borrow_transactions()

    assert len(transactions) == 1
    assert transactions[0]["student"] == "Alice"
    assert transactions[0]["book"] == "Database System Concepts"


def test_borrow_transaction_generates_due_date():
    """
    GIVEN a pending borrowing request exists
    WHEN the librarian approves the borrowing request
    THEN the system should generate borrow date and due date
    """
    approve_borrow_request(1)

    transaction = get_borrow_transactions()[0]

    assert transaction["borrow_date"] is not None
    assert transaction["due_date"] is not None


def test_due_date_follows_library_policy():
    """
    GIVEN a borrowing request is approved
    WHEN the system generates the due date
    THEN the due date should be 14 days after the borrow date
    """
    approve_borrow_request(1)

    transaction = get_borrow_transactions()[0]

    from datetime import date, timedelta

    expected_due_date = date.fromisoformat(transaction["borrow_date"]) + timedelta(
        days=14
    )

    assert transaction["due_date"] == expected_due_date.isoformat()


# ==================================================
# User Story 3:
# As a librarian, I want the system to record every
# borrowing transaction so that borrowing records
# remain complete and accurate.
# ==================================================


def test_borrowing_transaction_contains_complete_record():
    """
    GIVEN a borrowing request has been approved
    WHEN the system creates a borrowing transaction
    THEN the transaction should contain all required information
    """
    approve_borrow_request(1)

    transaction = get_borrow_transactions()[0]

    assert transaction["id"] is not None
    assert transaction["request_id"] == 1
    assert transaction["student"] == "Alice"
    assert transaction["book"] == "Database System Concepts"
    assert transaction["borrow_date"] is not None
    assert transaction["due_date"] is not None
    assert transaction["return_date"] is None
    assert transaction["status"] == "Borrowed"


def test_each_approved_request_creates_separate_transaction():
    """
    GIVEN multiple pending borrowing requests exist
    WHEN librarians approve multiple requests
    THEN each approval should create its own borrowing transaction
    """
    approve_borrow_request(1)
    approve_borrow_request(2)

    transactions = get_borrow_transactions()

    assert len(transactions) == 2
    assert transactions[0]["request_id"] != transactions[1]["request_id"]


# ==================================================
# User Story 4:
# As a student, I want the system to allow me to
# return borrowed books so that my borrowing record
# is updated.
# ==================================================


def test_student_can_request_book_return():
    """
    GIVEN a student has a borrowed book
    WHEN the student requests to return the book
    THEN the borrowing status should change to "Return Pending"
    """

    approve_borrow_request(1)

    result = request_book_return(1)

    assert result is True

    transaction = find_borrow_transaction(1)

    assert transaction is not None
    assert transaction["status"] == "Return Pending"


def test_student_cannot_request_return_for_invalid_transaction():
    """
    GIVEN a transaction ID that does not exist
    WHEN the student requests a return
    THEN the system should reject the request
    """

    result = request_book_return(999)

    assert result is False


def test_student_cannot_request_return_twice():
    """
    GIVEN a book is already pending return
    WHEN the student requests return again
    THEN the system should reject the duplicate request
    """

    approve_borrow_request(1)

    request_book_return(1)

    result = request_book_return(1)

    assert result is False
