# Author: Tan Wei Khye

import pytest

from modules.borrowing.services import (
    approve_borrow_request,
    confirm_book_return,
)


@pytest.fixture(autouse=True)
def fake_repository(monkeypatch):
    """
    Provide a valid borrowing and returning scenario.
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

    transaction = {
        "id": "TRAN001",
        "book_id": "BOOK001",
        "student_id": "USR001",
        "status": "Return Pending",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: book,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_request_status",
        lambda request_id, status: request.update({"status": status}),
    )

    monkeypatch.setattr(
        "modules.borrowing.services.add_borrow_transaction",
        lambda transaction_data: "TRAN001",
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_borrow_transaction",
        lambda transaction_id, data: transaction.update(data),
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_book",
        lambda book_id, data: book.update(data),
    )

    return {
        "request": request,
        "book": book,
        "transaction": transaction,
    }


def test_borrowing_decreases_available_copies(fake_repository):
    """
    GIVEN a book has one available copy
    WHEN the borrowing request is approved
    THEN the available copies decrease by one.
    """

    approve_borrow_request("REQ001")

    assert fake_repository["book"]["available_copies"] == 0


def test_confirm_return_increases_available_copies(fake_repository):
    """
    GIVEN a returned book has zero available copies
    WHEN the librarian confirms the return
    THEN the available copies increase by one.
    """

    fake_repository["book"]["available_copies"] = 0

    confirm_book_return("TRAN001")

    assert fake_repository["book"]["available_copies"] == 1


def test_failed_borrow_does_not_change_available_copies(
    fake_repository,
    monkeypatch,
):
    """
    GIVEN the book has no available copies
    WHEN borrowing approval is attempted
    THEN the available copies remain unchanged.
    """

    fake_repository["book"]["available_copies"] = 0

    result = approve_borrow_request("REQ001")

    assert result is False
    assert fake_repository["book"]["available_copies"] == 0


def test_invalid_return_does_not_change_available_copies(
    fake_repository,
):
    """
    GIVEN the transaction is already returned
    WHEN the librarian confirms the return again
    THEN the available copies remain unchanged.
    """

    fake_repository["transaction"]["status"] = "Returned"

    fake_repository["book"]["available_copies"] = 1

    result = confirm_book_return("TRAN001")

    assert result is False
    assert fake_repository["book"]["available_copies"] == 1
