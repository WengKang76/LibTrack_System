# Author: Tan Wei Khye

"""
Test cases for Scrum-1677:
Search borrowing request records using keywords.
"""

import pytest

from modules.borrowing.services import (
    get_filtered_pending_requests,
)


@pytest.fixture
def mock_requests(monkeypatch):

    requests = [
        {
            "id": "REQ001",
            "student_id": "USR001",
            "student": "Alice",
            "book_id": "BOOK001",
            "book": "Python Programming",
            "status": "Pending",
        },
    ]

    monkeypatch.setattr(
        "modules.borrowing.services.get_pending_requests",
        lambda: requests,
    )


def test_search_request_by_student_id(mock_requests):
    """
    Given a borrowing request belongs to a student

    When librarian searches using student ID

    Then matching request should be returned
    """

    result = get_filtered_pending_requests(
        keyword="USR001",
    )

    assert len(result) == 1
    assert result[0]["student_id"] == "USR001"


def test_search_request_by_book_title(mock_requests):
    """
    Given a borrowing request contains a book title

    When librarian searches using book title

    Then matching request should be returned
    """

    result = get_filtered_pending_requests(
        keyword="Python",
    )

    assert len(result) == 1
    assert result[0]["book"] == "Python Programming"
