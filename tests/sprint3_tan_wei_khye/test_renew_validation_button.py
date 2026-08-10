# Author: Tan Wei Khye

from unittest.mock import patch

from modules.borrowing.services import (
    get_renewal_unavailable_reason,
)


def test_renewal_available_when_no_reservation():
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
