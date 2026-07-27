import pytest

from modules.borrowing.services import (
    approve_borrow_request,
    get_borrow_approval_error,
)


@pytest.fixture(autouse=True)
def fake_repository(monkeypatch):
    """
    Provide default valid borrowing scenario.
    """

    request = {
        "id": "REQ001",
        "book_id": "BOOK001",
        "student_id": "USR001",
        "status": "Pending",
        "borrowing_period": 14,
        "request_date": "2026-07-27",
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

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: False,
    )


def test_student_cannot_borrow_same_book_twice(monkeypatch):
    """
    GIVEN the student already has an active borrowing transaction
    WHEN the librarian approves another request for the same book
    THEN the approval should be rejected.
    """

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: True,
    )

    result = approve_borrow_request("REQ001")

    assert result is False


def test_student_can_borrow_when_no_duplicate_exists(monkeypatch):
    """
    GIVEN the student has no active borrowing transaction
    WHEN the librarian approves the request
    THEN the borrowing transaction should be created.
    """

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: False,
    )

    result = approve_borrow_request("REQ001")

    assert result == "TRAN001"


def test_duplicate_borrow_returns_validation_message(monkeypatch):
    """
    GIVEN the student already borrowed the same book
    WHEN the system validates the approval
    THEN the duplicate borrowing message should be returned.
    """

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: True,
    )

    message = get_borrow_approval_error("REQ001")

    assert message == (
        "Student already has an active borrowing transaction for this book."
    )


def test_no_validation_error_when_borrow_is_allowed(monkeypatch):
    """
    GIVEN all borrowing conditions are satisfied
    WHEN the system validates the approval
    THEN no validation message should be returned.
    """

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: False,
    )

    message = get_borrow_approval_error("REQ001")

    assert message is None
