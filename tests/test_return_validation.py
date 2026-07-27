import pytest

from modules.borrowing.services import (
    request_book_return,
    confirm_book_return,
)


@pytest.fixture(autouse=True)
def fake_repository(monkeypatch):
    """
    Provide default borrowing scenario.
    Every test starts with:
    - valid pending request
    - valid book
    - no penalty
    - no duplicate borrowing
    - empty transactions
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

    # ==========================
    # Borrow Request
    # ==========================

    def fake_find_request(request_id):

        if request_id == "REQ001":
            return request

        return None

    def fake_update_request_status(request_id, status):

        request["status"] = status

    # ==========================
    # Borrow Transaction
    # ==========================

    def fake_add_borrow_transaction(transaction):

        transaction["id"] = "TRAN001"

        transactions.append(transaction)

        return "TRAN001"

    def fake_find_borrow_transaction(transaction_id):

        for transaction in transactions:

            if transaction["id"] == transaction_id:
                return transaction

        return None

    def fake_get_borrow_transactions():

        return transactions

    def fake_update_borrow_transaction(
        transaction_id,
        updates,
    ):

        for transaction in transactions:

            if transaction["id"] == transaction_id:

                transaction.update(updates)

    # ==========================
    # Book
    # ==========================

    def fake_find_book(book_id):

        if book_id == "BOOK001":

            return book

        return None

    def fake_update_book(
        book_id,
        updates,
    ):

        book.update(updates)

    # ==========================
    # Validation
    # ==========================

    def fake_has_outstanding_penalty(student_id):

        return False

    def fake_has_active_borrow_transaction(
        student_id,
        book_id,
    ):

        return False

    def fake_has_active_reservation(book_id):

        return False

    # ==========================
    # Apply monkeypatch
    # ==========================

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        fake_find_request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_request_status",
        fake_update_request_status,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.add_borrow_transaction",
        fake_add_borrow_transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        fake_find_borrow_transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.get_borrow_transactions",
        fake_get_borrow_transactions,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_borrow_transaction",
        fake_update_borrow_transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        fake_find_book,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_book",
        fake_update_book,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        fake_has_outstanding_penalty,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        fake_has_active_borrow_transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_reservation",
        fake_has_active_reservation,
    )


def test_return_invalid_transaction_returns_false():
    """
    GIVEN a transaction ID does not exist
    WHEN a return request is submitted
    THEN the system should reject it
    """

    result = request_book_return("INVALID001")

    assert result is False


def test_cannot_return_already_returned_book(monkeypatch):
    """
    GIVEN a transaction is already returned
    WHEN a student tries to return it again
    THEN the system should reject it
    """

    transaction = {
        "id": "TRAN001",
        "status": "Returned",
        "book_id": "BOOK001",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    result = request_book_return("TRAN001")

    assert result is False


def test_cannot_confirm_return_before_return_request(monkeypatch):
    """
    GIVEN a transaction is still Borrowed
    WHEN librarian confirms return directly
    THEN the system should reject it
    """

    transaction = {
        "id": "TRAN001",
        "status": "Borrowed",
        "book_id": "BOOK001",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    result = confirm_book_return("TRAN001")

    assert result is False
