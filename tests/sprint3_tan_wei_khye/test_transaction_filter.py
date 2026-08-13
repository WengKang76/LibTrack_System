# Author: Tan Wei Khye

"""
Test cases for Scrum-1676:
As a librarian, I want to filter borrowing transaction records
by status and other relevant criteria.
"""

import pytest

from modules.borrowing.services import (
    get_filtered_borrow_transactions,
)


@pytest.fixture
def mock_transactions(monkeypatch):

    transactions = [
        {
            "id": "TX001",
            "student_id": "USR001",
            "book_id": "BOOK001",
            "status": "Borrowed",
        },
        {
            "id": "TX002",
            "student_id": "USR002",
            "book_id": "BOOK002",
            "status": "Returned",
        },
    ]

    monkeypatch.setattr(
        "modules.borrowing.services.get_borrow_transactions",
        lambda: transactions,
    )


def test_filter_transaction_by_status(mock_transactions):
    """
    Given transactions have different statuses

    When librarian filters transactions by Borrowed status

    Then only active borrowed transactions are returned
    """

    result = get_filtered_borrow_transactions(
        status="Borrowed",
    )

    assert len(result) == 1
    assert result[0]["status"] == "Borrowed"
    assert result[0]["id"] == "TX001"
