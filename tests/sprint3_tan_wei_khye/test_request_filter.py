# Author: Tan Wei Khye

"""
Test cases for Scrum-1675:
As a librarian, I want to filter borrowing request records by status
and other relevant criteria, so that I can easily find and manage
specific requests.
"""

import pytest

from modules.borrowing.services import (
    get_filtered_pending_requests,
)


@pytest.fixture
def mock_requests(monkeypatch):
    """
    Provide sample borrowing requests.
    """

    requests = [
        {
            "id": "REQ001",
            "student_id": "USR001",
            "student": "Alice",
            "book_id": "BOOK001",
            "book": "Python Programming",
            "status": "Pending",
        },
        {
            "id": "REQ002",
            "student_id": "USR002",
            "student": "Bob",
            "book_id": "BOOK002",
            "book": "Database System",
            "status": "Approved",
        },
    ]

    monkeypatch.setattr(
        "modules.borrowing.services.get_pending_requests",
        lambda: requests,
    )


def test_filter_pending_request_by_status(mock_requests):
    """
    Given borrowing requests have different statuses

    When librarian filters requests by Pending status

    Then only pending requests should be returned
    """

    result = get_filtered_pending_requests(
        status="Pending",
    )

    assert len(result) == 1
    assert result[0]["status"] == "Pending"
    assert result[0]["id"] == "REQ001"
