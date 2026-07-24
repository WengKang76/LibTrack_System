"""Tests for borrowing service functions."""

from datetime import date, timedelta

import pytest

import modules.borrowing.services as service

import sys
from unittest.mock import MagicMock

from modules.borrowing.services import (
    approve_borrow_request,
    approve_renewal_request,
    cancel_renewal_request,
    close_borrow_transaction,
    confirm_book_return,
    manually_extend_due_date,
    reject_renewal_request,
    request_book_return,
    request_book_renewal,
)

sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()


@pytest.fixture(autouse=True)
def fake_repository(monkeypatch):

    transactions = []

    request = {
        "id": "REQ001",
        "book_id": "BOOK001",
        "student_id": "USR001",
        "status": "Pending",
        "borrowing_period": 14,
        "request_date": "2026-07-16",
    }

    book = {
        "id": "BOOK001",
        "title": "Database System Concepts",
        "available_copies": 1,
    }

    def fake_find_request(request_id):
        if request_id == "REQ001":
            return request

        return None

    def fake_update_request_status(
        request_id,
        status,
    ):
        request["status"] = status

    def fake_add_borrow_transaction(transaction):

        transaction["id"] = "TRAN001"

        transactions.append(transaction)

        return "TRAN001"

    def fake_get_borrow_transactions():

        return transactions

    def fake_find_borrow_transaction(transaction_id):

        for item in transactions:

            if item["id"] == transaction_id:

                return item

        return None

    def fake_update_borrow_transaction(
        transaction_id,
        updates,
    ):

        for item in transactions:

            if item["id"] == transaction_id:

                item.update(updates)

    def fake_find_book(book_id):

        if book_id == "BOOK001":

            return book

        return None

    def fake_update_book(
        book_id,
        updates,
    ):

        book.update(updates)

    monkeypatch.setattr("modules.borrowing.services.find_request", fake_find_request)

    monkeypatch.setattr(
        "modules.borrowing.services.update_request_status", fake_update_request_status
    )

    monkeypatch.setattr(
        "modules.borrowing.services.add_borrow_transaction", fake_add_borrow_transaction
    )

    monkeypatch.setattr(
        "modules.borrowing.services.get_borrow_transactions",
        fake_get_borrow_transactions,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_borrow_transaction",
        fake_find_borrow_transaction,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.update_borrow_transaction",
        fake_update_borrow_transaction,
    )

    monkeypatch.setattr("modules.borrowing.services.find_book", fake_find_book)

    monkeypatch.setattr("modules.borrowing.services.update_book", fake_update_book)

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_reservation", lambda book_id: False
    )

    yield
    transactions.clear()


# ==================================================
# User Story 1:
# As a librarian, I want to approve a borrowing request
# so that the book can be officially issued to student.
# ==================================================


def test_approve_pending_borrow_request():
    """
    GIVEN a borrow request exists with status "Pending"
    WHEN the librarian approves the borrowing request
    THEN the approval process should succeed and updated to "Approved"
    """
    result = approve_borrow_request("REQ001")

    assert result is not None


def test_approve_non_existing_request():
    """
    GIVEN a borrow request ID that does not exist in the system
    WHEN the librarian attempts to approve the invalid request
    THEN the system should reject the approval attempt
    """
    result = approve_borrow_request("REQ999")

    assert result is False


def test_cannot_approve_already_approved_request():
    """
    GIVEN a borrow request has already been approved
    WHEN the librarian attempts to approve the same request again
    THEN the system should prevent duplicate approval
    """
    approve_borrow_request("REQ001")

    result = approve_borrow_request("REQ001")

    assert result is False


# ==================================================
# User Story 2:
# As a librarian, I want the system to automatically
# generate a due date when a borrowing request is approved
# so that all borrowing periods follow library policy.
# ==================================================


def test_approval_creates_borrow_transaction():
    """
    GIVEN a pending borrowing request exists
    WHEN the librarian approves the borrowing request
    THEN the system should create a borrow transaction
    """
    approve_borrow_request("REQ001")

    transactions = service.get_borrow_transactions()

    assert len(transactions) == 1
    assert transactions[0]["student_id"] == "USR001"
    assert transactions[0]["book_id"] == "BOOK001"


def test_borrow_transaction_generates_due_date():
    """
    GIVEN a pending borrowing request exists
    WHEN the librarian approves the borrowing request
    THEN the system should generate borrow date and due date
    """
    approve_borrow_request("REQ001")

    transaction = service.get_borrow_transactions()[0]

    assert transaction["borrow_date"] is not None
    assert transaction["due_date"] is not None


def test_due_date_follows_library_policy():
    """
    GIVEN a borrowing request is approved
    WHEN the system generates the due date
    THEN the due date should be 14 days after the borrow date
    """
    approve_borrow_request("REQ001")

    transaction = service.get_borrow_transactions()[0]

    from datetime import date, timedelta

    expected_due_date = date.fromisoformat(transaction["borrow_date"]) + timedelta(
        days=14
    )

    assert transaction["due_date"] == expected_due_date.isoformat()


# ==================================================
# User Story 3:
# As a librarian, I want the system to record every
# borrowing transaction so that borrowing records
# remain complete and accurate.
# ==================================================


def test_borrowing_transaction_contains_complete_record():
    """
    GIVEN a borrowing request has been approved
    WHEN the system creates a borrowing transaction
    THEN the transaction should contain all required information
    """
    approve_borrow_request("REQ001")

    transaction = service.get_borrow_transactions()[0]

    assert transaction["request_id"] == "REQ001"
    assert transaction["student_id"] == "USR001"
    assert transaction["book_id"] == "BOOK001"
    assert transaction["borrow_date"] is not None
    assert transaction["due_date"] is not None
    assert transaction["return_date"] is None
    assert transaction["status"] == "Borrowed"


def test_each_approved_request_creates_separate_transaction():
    """
    GIVEN multiple pending borrowing requests exist
    WHEN librarians approve multiple requests
    THEN each approval should create its own borrowing transaction
    """
    approve_borrow_request("REQ001")

    transaction = service.get_borrow_transactions()[0]

    assert transaction["id"] == "TRAN001"


# ==================================================
# User Story 4:
# As a student, I want the system to allow me to
# return borrowed books so that my borrowing record
# is updated.
# ==================================================


def test_student_can_request_book_return():
    """
    GIVEN a student has a borrowed book
    WHEN the student requests to return the book
    THEN the borrowing status should change to "Return Pending"
    """

    approve_borrow_request("REQ001")

    result = request_book_return("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["status"] == "Return Pending"


def test_student_cannot_request_return_for_invalid_transaction():
    """
    GIVEN a transaction ID that does not exist
    WHEN the student requests a return
    THEN the system should reject the request
    """

    result = request_book_return("INVALID")

    assert result is False


def test_student_cannot_request_return_twice():
    """
    GIVEN a book is already pending return
    WHEN the student requests return again
    THEN the system should reject the duplicate request
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    result = request_book_return("TRAN001")

    assert result is False


# ==================================================
# User Story 5:
# As a librarian, I want to record book returns
# so that the system can update the book availability.
# ==================================================


def test_librarian_can_confirm_book_return():
    """
    GIVEN a transaction has a return request
    WHEN the librarian confirms the returned book
    THEN the transaction status should become Returned
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    result = confirm_book_return("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["status"] == "Returned"


def test_cannot_confirm_non_existing_return():
    """
    GIVEN a transaction ID does not exist
    WHEN the librarian confirms the return
    THEN the system should reject the request
    """

    result = confirm_book_return("INVALID")

    assert result is False


def test_cannot_confirm_book_without_return_request():
    """
    GIVEN a book is still being borrowed
    WHEN the librarian tries to confirm return
    THEN the system should reject the confirmation
    """

    approve_borrow_request("REQ001")

    result = confirm_book_return("TRAN001")

    assert result is False


# ==================================================
# User Story 6:
# As a librarian, I want the system to record every
# return transaction so that the borrowing history
# is properly maintained.
# ==================================================


def test_return_transaction_records_return_date():
    """
    GIVEN a book has been returned and confirmed by librarian
    WHEN the return process is completed
    THEN the system should record the return date
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction is not None
    assert transaction["status"] == "Returned"
    assert transaction["return_date"] is not None


def test_return_transaction_preserves_borrowing_history():
    """
    GIVEN a completed borrowing transaction
    WHEN the book is returned
    THEN the original borrowing record should still exist
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    transactions = service.get_borrow_transactions()

    assert len(transactions) == 1

    assert transactions[0]["request_id"] == "REQ001"


def test_returned_book_remains_in_transaction_history():
    """
    GIVEN a book has been returned
    WHEN the librarian views transaction history
    THEN the returned transaction should still be available
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction is not None


# ==================================================
# User Story 7:
# As a librarian, I want to confirm the returned book
# from returning student so that the book becomes
# available for other students.
# ==================================================


def test_confirm_return_updates_book_availability():
    """
    GIVEN a borrowed book has no available copies
    WHEN the librarian confirms the returned book
    THEN the book availability should increase
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    book = service.find_book("BOOK001")

    assert book["available_copies"] == 2


def test_return_without_matching_book_does_not_fail():
    """
    GIVEN a transaction exists but book information is unavailable
    WHEN the librarian confirms return
    THEN the return process should still complete
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    transaction = service.find_borrow_transaction("TRAN001")

    transaction["book_id"] = "UNKNOWN"

    result = confirm_book_return("TRAN001")

    assert result is True


# ==================================================
# User Story 8:
# As a student, I want to renew a borrowed book
# so that I can extend the borrowing period if
# necessary.
#
# The student submits a renewal request.
# Due date should not change until librarian approval.
# ==================================================


def test_student_can_request_book_renewal():
    """
    GIVEN a student has a borrowed book
    WHEN the student requests renewal
    THEN the renewal status should become Pending
    """

    approve_borrow_request("REQ001")

    result = request_book_renewal("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["renewal_status"] == "Pending"


def test_renewal_request_does_not_change_due_date():
    """
    GIVEN a student has a borrowed book
    WHEN the student submits a renewal request
    THEN the due date should remain unchanged
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    original_due_date = transaction["due_date"]

    request_book_renewal("TRAN001")

    assert transaction["due_date"] == original_due_date


def test_cannot_request_renewal_after_return():
    """
    GIVEN a student has returned the borrowed book
    WHEN the student requests renewal
    THEN the system should reject the request
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    result = request_book_renewal("TRAN001")

    assert result is False


def test_cannot_submit_duplicate_renewal_request():
    """
    GIVEN a student already has a pending renewal request
    WHEN the student requests renewal again
    THEN the system should reject the duplicate request
    """

    approve_borrow_request("REQ001")

    first_request = request_book_renewal("TRAN001")

    second_request = request_book_renewal("TRAN001")

    assert first_request is True
    assert second_request is False


# ==================================================
# User Story 9:
# As a student, I want the system to prevent renewal
# when another student has reserved the book so that
# the reservation queue is respected.
# ==================================================


def test_cannot_renew_book_with_active_reservation(monkeypatch):
    """
    GIVEN another student has reserved the borrowed book
    WHEN the student requests renewal
    THEN the renewal request should be rejected
    """

    approve_borrow_request("REQ001")

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_reservation", lambda book_id: True
    )

    result = request_book_renewal("TRAN001")

    assert result is False


def test_can_renew_book_without_reservation():
    """
    GIVEN no student has reserved the borrowed book
    WHEN the student requests renewal
    THEN the renewal request should be created
    """

    approve_borrow_request("REQ001")

    result = request_book_renewal("TRAN001")

    assert result is True


# ==================================================
# User Story 10:
# As a librarian, I want to manually extend the due
# date of any borrowed book without a prior request,
# so that I can correct system errors or handle
# emergency situations.
#
# The librarian selects a new valid due date.
# The system updates the borrowing period and
# informs the student.
# ==================================================


def test_librarian_can_manually_extend_due_date():
    """
    GIVEN a student has an active borrowed book
    WHEN the librarian manually extends the due date
    THEN the due date should be updated successfully
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    new_due_date = (
        date.fromisoformat(transaction["due_date"]) + timedelta(days=7)
    ).isoformat()

    result = manually_extend_due_date(
        "TRAN001",
        new_due_date,
    )

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["due_date"] == new_due_date

    assert transaction["renewal_status"] == ("Manual Extension")


def test_manual_extension_creates_student_message():
    """
    GIVEN a librarian extends a borrowed book
    WHEN the extension succeeds
    THEN a message should be created for the student
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    new_due_date = (
        date.fromisoformat(transaction["due_date"]) + timedelta(days=10)
    ).isoformat()

    manually_extend_due_date(
        "TRAN001",
        new_due_date,
    )

    assert transaction["show_renewal_message"] is True

    assert transaction["renewal_message"] != ""


def test_cannot_manually_extend_to_before_current_due_date():
    """
    GIVEN a borrowed book has an existing due date
    WHEN the librarian selects an earlier date
    THEN the extension should fail
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    old_due_date = transaction["due_date"]

    earlier_date = (date.fromisoformat(old_due_date) - timedelta(days=5)).isoformat()

    result = manually_extend_due_date(
        "TRAN001",
        earlier_date,
    )

    assert result is False


def test_cannot_manually_extend_non_existing_transaction():
    """
    GIVEN a transaction does not exist
    WHEN librarian attempts manual extension
    THEN the system should reject it
    """

    result = manually_extend_due_date(
        "INVALID",
        "2026-08-20",
    )

    assert result is False


def test_cannot_manually_extend_returned_book():
    """
    GIVEN a book has already been returned
    WHEN librarian attempts manual extension
    THEN the system should reject it
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    transaction["status"] = "Returned"

    result = manually_extend_due_date(
        "TRAN001",
        "2026-08-20",
    )

    assert result is False


# ==================================================
# User Story 11:
# As a librarian, I want to approve a valid extension
# request with one click so that I can process requests
# efficiently.
#
# The librarian approves a pending renewal request.
# The due date is extended and renewal status changes
# to Approved.
# ==================================================


def test_librarian_can_approve_renewal_request():
    """
    GIVEN a student has submitted a renewal request
    WHEN the librarian approves the renewal request
    THEN the renewal status should become Approved
    AND the due date should be extended
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    original_due_date = transaction["due_date"]

    request_book_renewal("TRAN001")

    result = approve_renewal_request("TRAN001")

    assert result is True

    assert transaction["renewal_status"] == "Approved"

    assert transaction["due_date"] != original_due_date


def test_approved_renewal_extends_due_date_by_14_days():
    """
    GIVEN a pending renewal request exists
    WHEN the librarian approves the request
    THEN the due date should increase by 14 days
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    original_due_date = date.fromisoformat(transaction["due_date"])

    request_book_renewal("TRAN001")

    approve_renewal_request("TRAN001")

    expected_due_date = original_due_date + timedelta(days=14)

    assert transaction["due_date"] == expected_due_date.isoformat()


def test_cannot_approve_non_existing_renewal_request():
    """
    GIVEN a transaction ID does not exist
    WHEN the librarian approves renewal
    THEN the system should reject the request
    """

    result = approve_renewal_request("REQ999")

    assert result is False


def test_cannot_approve_already_approved_renewal_request():
    """
    GIVEN a renewal request has already been approved
    WHEN the librarian approves it again
    THEN the system should reject the duplicate approval
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    approve_renewal_request("TRAN001")

    result = approve_renewal_request("TRAN001")

    assert result is False


# ==================================================
# User Story 12:
# As a librarian, I want to reject an invalid request
# so that the student cannot extend their borrowed
# book with an invalid reason.
#
# The librarian rejects a pending renewal request.
# The renewal status becomes Rejected and the student
# receives a rejection message.
# ==================================================


def test_librarian_can_reject_renewal_request():
    """
    GIVEN a student has submitted a renewal request
    WHEN the librarian rejects the renewal request
    THEN the renewal status should become Rejected
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    result = reject_renewal_request("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction is not None
    assert transaction["renewal_status"] == "Rejected"


def test_rejected_renewal_does_not_change_due_date():
    """
    GIVEN a student has submitted a renewal request
    WHEN the librarian rejects the request
    THEN the due date should remain unchanged
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    original_due_date = transaction["due_date"]

    request_book_renewal("TRAN001")

    reject_renewal_request("TRAN001")

    assert transaction["due_date"] == original_due_date


def test_rejected_renewal_creates_student_message():
    """
    GIVEN a pending renewal request exists
    WHEN the librarian rejects the request
    THEN a rejection message should be created
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    reject_renewal_request("TRAN001")

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["show_renewal_message"] is True

    assert transaction["renewal_message"] != ""


def test_cannot_reject_non_existing_renewal_request():
    """
    GIVEN a transaction ID does not exist
    WHEN the librarian rejects renewal
    THEN the system should return False
    """

    result = reject_renewal_request("REQ999")

    assert result is False


def test_cannot_reject_approved_renewal_request():
    """
    GIVEN a renewal request has already been approved
    WHEN the librarian rejects it afterwards
    THEN the system should reject the action
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    approve_renewal_request("TRAN001")

    result = reject_renewal_request("TRAN001")

    assert result is False


# ==================================================
# User Story 13:
# As a student, I want to cancel my pending extension
# request, so that I can withdraw my request if I no
# longer need the book or plan to return it early.
#
# The student cancels a pending renewal request.
# The renewal status becomes Cancelled and the due
# date remains unchanged.
# ==================================================


def test_student_can_cancel_pending_renewal_request():
    """
    GIVEN a student has submitted a renewal request
    WHEN the student cancels the pending request
    THEN the renewal status should become Cancelled
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    result = cancel_renewal_request("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction is not None
    assert transaction["renewal_status"] == "Cancelled"


def test_cancelled_renewal_does_not_change_due_date():
    """
    GIVEN a student has a pending renewal request
    WHEN the student cancels the request
    THEN the due date should remain unchanged
    """

    approve_borrow_request("REQ001")

    transaction = service.find_borrow_transaction("TRAN001")

    original_due_date = transaction["due_date"]

    request_book_renewal("TRAN001")

    cancel_renewal_request("TRAN001")

    assert transaction["due_date"] == original_due_date


def test_cancelled_renewal_creates_student_message():
    """
    GIVEN a pending renewal request exists
    WHEN the student cancels the request
    THEN a cancellation message should be created
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    cancel_renewal_request("TRAN001")

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction["show_renewal_message"] is True

    assert transaction["renewal_message"] != ""


def test_cannot_cancel_non_existing_renewal_request():
    """
    GIVEN a transaction ID does not exist
    WHEN the student cancels renewal
    THEN the system should reject the action
    """

    result = cancel_renewal_request("REQ999")

    assert result is False


def test_cannot_cancel_approved_renewal_request():
    """
    GIVEN a renewal request has already been approved
    WHEN the student attempts to cancel it
    THEN the system should reject the action
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    approve_renewal_request("TRAN001")

    result = cancel_renewal_request("TRAN001")

    assert result is False


def test_cannot_cancel_rejected_renewal_request():
    """
    GIVEN a renewal request has already been rejected
    WHEN the student attempts to cancel it
    THEN the system should reject the action
    """

    approve_borrow_request("REQ001")

    request_book_renewal("TRAN001")

    reject_renewal_request("TRAN001")

    result = cancel_renewal_request("TRAN001")

    assert result is False


# ==================================================
# User Story 14:
# As a librarian, I want to close a borrowing
# transaction after all books are returned and
# penalties are settled so that the borrowing
# process is completed.
#
# The librarian closes a returned borrowing
# transaction to complete the borrowing lifecycle.
# ==================================================


def test_librarian_can_close_returned_transaction():
    """
    GIVEN a borrowing transaction has been returned
    WHEN the librarian closes the transaction
    THEN the transaction status should become Closed
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    result = close_borrow_transaction("TRAN001")

    assert result is True

    transaction = service.find_borrow_transaction("TRAN001")

    assert transaction is not None
    assert transaction["status"] == "Closed"


def test_cannot_close_borrowed_transaction():
    """
    GIVEN a borrowing transaction is still borrowed
    WHEN the librarian attempts to close it
    THEN the system should reject the request
    """

    approve_borrow_request("REQ001")

    result = close_borrow_transaction("TRAN001")

    assert result is False


def test_cannot_close_return_pending_transaction():
    """
    GIVEN a borrowing transaction is waiting for return confirmation
    WHEN the librarian attempts to close it
    THEN the system should reject the request
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    result = close_borrow_transaction("TRAN001")

    assert result is False


def test_cannot_close_non_existing_transaction():
    """
    GIVEN a transaction ID does not exist
    WHEN the librarian attempts to close it
    THEN the system should reject the request
    """

    result = close_borrow_transaction("REQ999")

    assert result is False


def test_cannot_close_already_closed_transaction():
    """
    GIVEN a borrowing transaction has already been closed
    WHEN the librarian attempts to close it again
    THEN the system should reject the duplicate action
    """

    approve_borrow_request("REQ001")

    request_book_return("TRAN001")

    confirm_book_return("TRAN001")

    close_borrow_transaction("TRAN001")

    result = close_borrow_transaction("TRAN001")

    assert result is False


# ==================================================
# End of Test Cases
# ==================================================
