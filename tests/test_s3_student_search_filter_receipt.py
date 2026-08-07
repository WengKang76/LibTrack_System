from modules.penalty_transaction.routes import (
    filter_student_penalty_records,
    build_payment_receipt,
    DEMO_PENALTIES,
)


def test_s3_01_filter_penalty_records_by_status():
    penalties = [
        {
            "penalty_id": "P001",
            "book_title": "Python Basics",
            "status": "Outstanding",
            "payment_method": "-"
        },
        {
            "penalty_id": "P002",
            "book_title": "Web Development",
            "status": "Paid",
            "payment_method": "Cash"
        }
    ]

    result = filter_student_penalty_records(
        penalties,
        status_filter="Paid"
    )

    assert len(result) == 1
    assert result[0]["penalty_id"] == "P002"


def test_s3_01_search_penalty_records_by_book_title():
    penalties = [
        {
            "penalty_id": "P001",
            "book_title": "Python Basics",
            "status": "Outstanding",
            "payment_method": "-"
        },
        {
            "penalty_id": "P002",
            "book_title": "Web Development",
            "status": "Paid",
            "payment_method": "Cash"
        }
    ]

    result = filter_student_penalty_records(
        penalties,
        keyword="Python"
    )

    assert len(result) == 1
    assert result[0]["book_title"] == "Python Basics"


def test_s3_01_filter_penalty_records_by_payment_method():
    penalties = [
        {
            "penalty_id": "P001",
            "book_title": "Python Basics",
            "status": "Paid",
            "payment_method": "Credit Card"
        },
        {
            "penalty_id": "P002",
            "book_title": "Web Development",
            "status": "Paid",
            "payment_method": "Cash"
        }
    ]

    result = filter_student_penalty_records(
        penalties,
        payment_method_filter="Cash"
    )

    assert len(result) == 1
    assert result[0]["payment_method"] == "Cash"


def test_s3_01_no_matching_penalty_records():
    penalties = [
        {
            "penalty_id": "P001",
            "book_title": "Python Basics",
            "status": "Outstanding",
            "payment_method": "-"
        }
    ]

    result = filter_student_penalty_records(
        penalties,
        keyword="Java"
    )

    assert len(result) == 0


def test_s3_02_build_payment_receipt_for_paid_penalty():
    DEMO_PENALTIES["P_S3_RECEIPT"] = {
        "student_id": "S001",
        "book_title": "Database System",
        "penalty_reason": "Overdue book",
        "penalty_amount": 10.00,
        "status": "Paid",
        "payment_method": "Cash",
        "paid_date": "2026-08-05 20:00:00",
        "paid_by": "S001"
    }

    success, message, receipt = build_payment_receipt(
        "P_S3_RECEIPT",
        "S001"
    )

    assert success is True
    assert receipt["penalty_id"] == "P_S3_RECEIPT"
    assert receipt["student_id"] == "S001"
    assert receipt["payment_amount"] == 10.00
    assert receipt["payment_method"] == "Cash"
    assert receipt["payment_status"] == "Paid"


def test_s3_02_receipt_not_available_for_unpaid_penalty():
    DEMO_PENALTIES["P_S3_UNPAID"] = {
        "student_id": "S001",
        "book_title": "Database System",
        "penalty_reason": "Overdue book",
        "penalty_amount": 10.00,
        "status": "Outstanding"
    }

    success, message, receipt = build_payment_receipt(
        "P_S3_UNPAID",
        "S001"
    )

    assert success is False
    assert receipt is None
    assert "only available after successful payment" in message