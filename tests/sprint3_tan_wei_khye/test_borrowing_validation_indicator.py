# Author: Tan Wei Khye
# Test cases for Scrum 1674


from modules.borrowing.services import (
    get_borrow_approval_error,
)


def test_valid_borrow_request_has_no_validation_error(monkeypatch):
    # GIVEN a pending borrow request with an available book,
    # and the student has no outstanding penalty or active borrowing transaction,
    # WHEN the system checks the borrow request validation status,
    # THEN the request should return no validation error and be marked as ready for approval.

    request = {
        "id": "REQ001",
        "student_id": "USR001",
        "book_id": "BOOK001",
        "status": "Pending",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: {
            "available_copies": 3,
            "status": "Available",
        },
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: False,
    )

    result = get_borrow_approval_error("REQ001")

    assert result is None


def test_validation_detects_unpaid_penalty(monkeypatch):
    # GIVEN a pending borrow request from a student with outstanding unpaid penalties,
    # WHEN the system checks the borrow request validation status,
    # THEN the system should return an error message indicating that the student has unpaid penalties.

    request = {
        "id": "REQ002",
        "student_id": "USR002",
        "book_id": "BOOK002",
        "status": "Pending",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: True,
    )

    result = get_borrow_approval_error("REQ002")

    assert result == "Student has outstanding unpaid penalties."


def test_validation_detects_unavailable_book(monkeypatch):
    # GIVEN a pending borrow request for a book with no available copies,
    # WHEN the system checks the borrow request validation status,
    # THEN the system should return an error message indicating that the book is currently unavailable.

    request = {
        "id": "REQ003",
        "student_id": "USR003",
        "book_id": "BOOK003",
        "status": "Pending",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: {
            "available_copies": 0,
            "status": "Unavailable",
        },
    )

    result = get_borrow_approval_error("REQ003")

    assert result == "Book is currently unavailable."


def test_validation_detects_duplicate_borrowing(monkeypatch):
    # GIVEN a pending borrow request where the student already has an active borrowing transaction for the same book,
    # WHEN the system checks the borrow request validation status,
    # THEN the system should return an error message indicating that the student already has an active borrowing transaction for the book.

    request = {
        "id": "REQ004",
        "student_id": "USR004",
        "book_id": "BOOK004",
        "status": "Pending",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_outstanding_penalty",
        lambda student_id: False,
    )

    monkeypatch.setattr(
        "modules.borrowing.services.find_book",
        lambda book_id: {
            "available_copies": 2,
            "status": "Available",
        },
    )

    monkeypatch.setattr(
        "modules.borrowing.services.has_active_borrow_transaction",
        lambda student_id, book_id: True,
    )

    result = get_borrow_approval_error("REQ004")

    assert (
        result == "Student already has an active borrowing transaction for this book."
    )


def test_processed_request_returns_error(monkeypatch):
    # GIVEN a borrow request that has already been processed,
    # WHEN the system checks the borrow request validation status,
    # THEN the system should return an error message indicating that the request has already been processed.

    request = {
        "id": "REQ005",
        "student_id": "USR005",
        "book_id": "BOOK005",
        "status": "Approved",
    }

    monkeypatch.setattr(
        "modules.borrowing.services.find_request",
        lambda request_id: request,
    )

    result = get_borrow_approval_error("REQ005")

    assert result == "This borrow request has already been processed."
