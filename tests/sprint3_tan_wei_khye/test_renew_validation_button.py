# Author: Tan Wei Khye
"""
Test cases for Scrum-1680:

"""

from unittest.mock import patch

from modules.borrowing.services import (
    get_renewal_unavailable_reason,
)


def test_renewal_available_when_no_reservation():
    """
    Given the student has a borrowed book with no active reservation
    When the system checks the book's renewal availability
    Then the system should allow the student to renew the book
    """

    transaction = {
        "id": "T001",
        "book_id": "BOOK001",
        "status": "Borrowed",
        "renewal_status": "None",
    }

    with patch(
        "modules.borrowing.services.find_borrow_transaction",
        return_value=transaction,
    ), patch(
        "modules.borrowing.services.has_active_reservation",
        return_value=False,
    ):
        result = get_renewal_unavailable_reason("T001")

    assert result is None


def test_renewal_unavailable_when_book_is_reserved():
    """
    Given the student has a borrowed book that has an active pending reservation
    When the system checks the book's renewal availability
    Then the system should prevent renewal and display "Renewal unavailable: Book is reserved by another student."
    """

    transaction = {
        "id": "T002",
        "book_id": "BOOK002",
        "status": "Borrowed",
        "renewal_status": "None",
    }

    with patch(
        "modules.borrowing.services.find_borrow_transaction",
        return_value=transaction,
    ), patch(
        "modules.borrowing.services.has_active_reservation",
        return_value=True,
    ):
        result = get_renewal_unavailable_reason("T002")

    assert result == "Renewal unavailable: Book is reserved by another student."


def test_renewal_unavailable_when_request_is_already_pending():
    """
    Given the student has a borrowed book with an existing pending renewal request
    When the system checks the book's renewal availability
    Then the system should prevent another renewal request and display "Renewal request is already pending."
    """

    transaction = {
        "id": "T003",
        "book_id": "BOOK003",
        "status": "Borrowed",
        "renewal_status": "Pending",
    }

    with patch(
        "modules.borrowing.services.find_borrow_transaction",
        return_value=transaction,
    ):
        result = get_renewal_unavailable_reason("T003")

    assert result == "Renewal request is already pending."
