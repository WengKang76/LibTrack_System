"""
Tests for Sprint 2 borrowing approval validation.

Covers:
- Scrum-1214: Student eligibility check
- Scrum-1215: Book availability check
"""

import pytest

from modules.borrowing.services import approve_borrow_request


@pytest.fixture
def mock_borrowing_dependencies(monkeypatch):
    """
    Provide default valid borrowing scenario.
    """

    request = {
        "id": "REQ001",
        "book_id": "BOOK001",
        "student_id": "USR001",
        "status": "Pending",
    }

    book = {
        "id": "BOOK001",
        "title": "Database System Concepts",
        "available_copies": 1,
    }

    transactions = []

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: book,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_request_status",
        lambda request_id, status: request.update({"status": status}),
    )

    monkeypatch.setattr(
        "modules.borrowing.services.add_borrow_transaction",
        lambda transaction: transactions.append(transaction) or "TRAN001",
    )

    return request, book, transactions


# ==================================================
# Scrum-1214
# ==================================================


def test_student_with_outstanding_penalty_cannot_borrow(
    monkeypatch,
    mock_borrowing_dependencies,
):
    """
    GIVEN a student has an outstanding penalty
    WHEN the librarian approves the borrowing request
    THEN the approval should be rejected
    """

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: True,
    )

    result = approve_borrow_request("REQ001")

    assert result is False


def test_student_without_penalty_can_borrow(
    mock_borrowing_dependencies,
):
    """
    GIVEN a student has no outstanding penalty
    WHEN the librarian approves the borrowing request
    THEN the approval should succeed
    """

    result = approve_borrow_request("REQ001")

    assert result == "TRAN001"


# ==================================================
# Scrum-1215
# ==================================================


def test_cannot_borrow_book_with_no_available_copy(
    monkeypatch,
    mock_borrowing_dependencies,
):
    """
    GIVEN a book has zero available copies
    WHEN the librarian approves borrowing
    THEN the approval should be rejected
    """

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: {
            "id": "BOOK001",
            "available_copies": 0,
        },
    )

    result = approve_borrow_request("REQ001")

    assert result is False


def test_can_borrow_book_with_available_copy(
    mock_borrowing_dependencies,
):
    """
    GIVEN a book has available copies
    WHEN the librarian approves borrowing
    THEN the approval should succeed
    """

    result = approve_borrow_request("REQ001")

    assert result == "TRAN001"
