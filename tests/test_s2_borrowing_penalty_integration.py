import copy

import pytest

from modules.penalty_transaction import routes as penalty_routes


@pytest.fixture(autouse=True)
def reset_demo_data():
    original_penalties = copy.deepcopy(penalty_routes.DEMO_PENALTIES)
    original_borrow_requests = copy.deepcopy(penalty_routes.DEMO_BORROW_REQUESTS)

    penalty_routes.DEMO_PENALTIES["S2B001"] = {
        "penalty_id": "S2B001",
        "student_id": "S001",
        "transaction_id": "T001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "penalty_amount": 10.00,
        "status": "Outstanding",
    }

    penalty_routes.DEMO_PENALTIES["S2B002"] = {
        "penalty_id": "S2B002",
        "student_id": "S002",
        "transaction_id": "T002",
        "book_id": "B002",
        "book_title": "Database System",
        "penalty_amount": 15.00,
        "status": "Paid",
    }

    penalty_routes.DEMO_PENALTIES["S2B003"] = {
        "penalty_id": "S2B003",
        "student_id": "S003",
        "transaction_id": "T003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "penalty_amount": 20.00,
        "status": "Waived",
    }

    penalty_routes.DEMO_BORROW_REQUESTS["BR1083_BLOCK"] = {
        "request_id": "BR1083_BLOCK",
        "student_id": "S001",
        "book_id": "B010",
        "book_title": "Computer Security",
        "request_date": "2026-07-29",
        "status": "Pending",
    }

    penalty_routes.DEMO_BORROW_REQUESTS["BR1083_ALLOW"] = {
        "request_id": "BR1083_ALLOW",
        "student_id": "S002",
        "book_id": "B011",
        "book_title": "Artificial Intelligence",
        "request_date": "2026-07-29",
        "status": "Pending",
    }

    penalty_routes.DEMO_BORROW_REQUESTS["BR1083_NOT_PENDING"] = {
        "request_id": "BR1083_NOT_PENDING",
        "student_id": "S003",
        "book_id": "B012",
        "book_title": "Web Development",
        "request_date": "2026-07-29",
        "status": "Approved",
    }

    yield

    penalty_routes.DEMO_PENALTIES.clear()
    penalty_routes.DEMO_PENALTIES.update(original_penalties)

    penalty_routes.DEMO_BORROW_REQUESTS.clear()
    penalty_routes.DEMO_BORROW_REQUESTS.update(original_borrow_requests)


def test_check_student_borrowing_eligibility_blocks_unpaid_penalty():
    success, message, unpaid_penalties = (
        penalty_routes.check_student_borrowing_eligibility("S001")
    )

    assert success is False
    assert (
        message
        == "Borrowing approval blocked because the student has unpaid penalties."
    )
    assert len(unpaid_penalties) >= 1


def test_check_student_borrowing_eligibility_allows_paid_penalty_only():
    success, message, unpaid_penalties = (
        penalty_routes.check_student_borrowing_eligibility("S002")
    )

    assert success is True
    assert (
        message
        == "Student has no unpaid penalties and can proceed with borrowing approval."
    )
    assert unpaid_penalties == []


def test_check_student_borrowing_eligibility_allows_waived_penalty_only():
    success, message, unpaid_penalties = (
        penalty_routes.check_student_borrowing_eligibility("S003")
    )

    assert success is True
    assert unpaid_penalties == []


def test_check_student_borrowing_eligibility_rejects_missing_student_id():
    success, message, unpaid_penalties = (
        penalty_routes.check_student_borrowing_eligibility("")
    )

    assert success is False
    assert message == "Student ID is required for borrowing approval."
    assert unpaid_penalties == []


def test_borrow_approval_blocked_when_student_has_unpaid_penalty():
    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR1083_BLOCK", "Librarian"
    )

    assert success is False
    assert (
        message
        == "Borrowing approval blocked because the student has unpaid penalties."
    )
    assert penalty_routes.DEMO_BORROW_REQUESTS["BR1083_BLOCK"]["status"] == "Pending"


def test_borrow_approval_success_when_student_has_no_unpaid_penalty():
    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR1083_ALLOW", "Librarian"
    )

    assert success is True
    assert message == "Borrow request approved successfully."
    assert penalty_routes.DEMO_BORROW_REQUESTS["BR1083_ALLOW"]["status"] == "Approved"
    assert (
        penalty_routes.DEMO_BORROW_REQUESTS["BR1083_ALLOW"]["approved_by"]
        == "Librarian"
    )
    assert (
        penalty_routes.DEMO_BORROW_REQUESTS["BR1083_ALLOW"]["last_action"]
        == "Approve Borrow Request"
    )


def test_borrow_approval_rejects_non_pending_request():
    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR1083_NOT_PENDING", "Librarian"
    )

    assert success is False
    assert message == "Only pending borrow requests can be approved."
