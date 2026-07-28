# Author: Tan Wei Khye

import pytest

from modules.borrowing.services import close_borrow_transaction


@pytest.fixture
def mock_transaction(monkeypatch):
    """
    Default borrowing transaction fixture.
    """

    transaction = {
        "id": "TR001",
        "student_id": "USR001",
        "book_id": "BOOK001",
        "status": "Exception Completed",
    }

    updated_data = {}

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_borrow_transaction",
        lambda transaction_id, data: updated_data.update(data),
    )

    return transaction, updated_data


def test_can_close_transaction_after_exception_completed(mock_transaction):

    transaction, updated_data = mock_transaction

    result = close_borrow_transaction("TR001")

    assert result is True
    assert updated_data["status"] == "Closed"


def test_cannot_close_transaction_when_exception_not_completed(monkeypatch):

    transaction = {
        "id": "TR002",
        "status": "Rejected",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    result = close_borrow_transaction("TR002")

    assert result is False


def test_cannot_close_active_borrow_transaction(monkeypatch):

    transaction = {
        "id": "TR003",
        "status": "Borrowed",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    result = close_borrow_transaction("TR003")

    assert result is False


def test_can_close_returned_transaction(monkeypatch):

    transaction = {
        "id": "TR004",
        "status": "Returned",
    }

    updated_data = {}

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        lambda transaction_id: transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_borrow_transaction",
        lambda transaction_id, data: updated_data.update(data),
    )

    result = close_borrow_transaction("TR004")

    assert result is True
    assert updated_data["status"] == "Closed"
