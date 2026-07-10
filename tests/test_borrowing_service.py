"""Tests for borrowing service functions."""

import pytest

from modules.borrowing.repository import borrow_requests, find_request
from modules.borrowing.services import approve_borrow_request


@pytest.fixture(autouse=True)
def reset_borrow_requests():
    """Reset borrow request repository before each test."""
    borrow_requests.clear()

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
