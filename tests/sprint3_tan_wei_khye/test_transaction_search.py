# Author: Tan Wei Khye

"""
Test cases for Scrum-1678:
Search borrowing transaction records using keywords.
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
            "student": "Alice",
            "book_id": "BOOK001",
            "book": "Python Programming",
            "status": "Borrowed",
        },
    ]

    monkeypatch.setattr(
        "modules.borrowing.services.get_borrow_transactions",
        lambda: transactions,
    )


def test_search_transaction_by_student_id(mock_transactions):
    """
    Given a transaction belongs to a student

    When librarian searches student ID

    Then matching transaction should appear
    """

    result = get_filtered_borrow_transactions(
        keyword="USR001",
    )

    assert len(result) == 1
    assert result[0]["student_id"] == "USR001"


def test_search_transaction_by_book_title(mock_transactions):
    """
    Given a transaction contains a book title

    When librarian searches book title

    Then matching transaction should appear
    """

    result = get_filtered_borrow_transactions(
        keyword="Python",
    )

    assert len(result) == 1
    assert result[0]["book"] == "Python Programming"
