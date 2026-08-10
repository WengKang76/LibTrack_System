# Author: Tan Wei Khye

from unittest.mock import patch

from modules.borrowing.services import get_all_borrow_transactions


def test_closed_transaction_is_removed_from_active_transactions():
    """
    Given the borrowing transaction list contains a closed transaction
    When the system retrieves active borrowing transactions
    Then the closed transaction should not be included in the result
    """
    transactions = [
        {
            "id": "T001",
            "status": "Borrowed",
        },
        {
            "id": "T002",
            "status": "Closed",
        },
    ]

    with patch(
        "modules.borrowing.services.get_borrow_transactions",
        return_value=transactions,
    ):
        result = get_all_borrow_transactions()

    assert len(result) == 1
    assert result[0]["id"] == "T001"


def test_active_transactions_are_kept():
    """
    Given the borrowing transaction list contains active and completed transactions
    When the system retrieves active borrowing transactions
    Then all non-closed transactions should remain in the result
    """
    transactions = [
        {
            "id": "T001",
            "status": "Borrowed",
        },
        {
            "id": "T002",
            "status": "Return Pending",
        },
        {
            "id": "T003",
            "status": "Returned",
        },
        {
            "id": "T004",
            "status": "Exception Completed",
        },
    ]

    with patch(
        "modules.borrowing.services.get_borrow_transactions",
        return_value=transactions,
    ):
        result = get_all_borrow_transactions()

    assert len(result) == 4
    assert [transaction["id"] for transaction in result] == [
        "T001",
        "T002",
        "T003",
        "T004",
    ]


def test_all_transactions_are_returned_when_none_are_closed():
    """
    Given there are no closed borrowing transactions
    When the system retrieves active borrowing transactions
    Then all borrowing transactions should be returned
    """

    transactions = [
        {
            "id": "T001",
            "status": "Borrowed",
        },
        {
            "id": "T002",
            "status": "Returned",
        },
    ]

    with patch(
        "modules.borrowing.services.get_borrow_transactions",
        return_value=transactions,
    ):
        result = get_all_borrow_transactions()

    assert result == transactions
