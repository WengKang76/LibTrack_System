from modules.penalty_transaction.routes import (
    search_librarian_penalty_records,
    validate_dynamic_payment_details,
    build_payment_confirmation_summary,
    get_user_friendly_payment_message,
)


def test_s3_03_librarian_search_penalty_by_student_id():
    penalties = [
        {
            "penalty_id": "P001",
            "student_id": "S001",
            "student_name": "Ali Tan",
            "book_title": "Python Programming",
        },
        {
            "penalty_id": "P002",
            "student_id": "S002",
            "student_name": "Mei Ling",
            "book_title": "Database System",
        },
    ]

    result = search_librarian_penalty_records(
        penalties,
        "S001"
    )

    assert len(result) == 1
    assert result[0]["student_id"] == "S001"


def test_s3_03_librarian_search_penalty_by_student_name():
    penalties = [
        {
            "penalty_id": "P001",
            "student_id": "S001",
            "student_name": "Ali Tan",
            "book_title": "Python Programming",
        },
        {
            "penalty_id": "P002",
            "student_id": "S002",
            "student_name": "Mei Ling",
            "book_title": "Database System",
        },
    ]

    result = search_librarian_penalty_records(
        penalties,
        "Mei"
    )

    assert len(result) == 1
    assert result[0]["student_name"] == "Mei Ling"


def test_s3_03_librarian_search_no_result():
    penalties = [
        {
            "penalty_id": "P001",
            "student_id": "S001",
            "student_name": "Ali Tan",
        }
    ]

    result = search_librarian_penalty_records(
        penalties,
        "S999"
    )

    assert len(result) == 0


def test_s3_04_validate_visa_payment_details():
    form_data = {
        "card_holder": "Ali Tan",
        "card_number": "4111111111111111",
        "expiry_date": "12/28",
        "cvv": "123"
    }

    success, message = validate_dynamic_payment_details(
        "Visa",
        form_data
    )

    assert success is True


def test_s3_04_validate_paypal_payment_details():
    form_data = {
        "paypal_email": "student@example.com"
    }

    success, message = validate_dynamic_payment_details(
        "PayPal",
        form_data
    )

    assert success is True


def test_s3_04_reject_missing_paypal_email():
    form_data = {
        "paypal_email": ""
    }

    success, message = validate_dynamic_payment_details(
        "PayPal",
        form_data
    )

    assert success is False
    assert "PayPal email is required" in message


def test_s3_05_build_payment_confirmation_summary():
    penalty = {
        "penalty_id": "P001",
        "student_id": "S001",
        "book_title": "Python Programming",
        "penalty_reason": "Overdue book",
        "penalty_amount": 5.00,
        "status": "Outstanding"
    }

    summary = build_payment_confirmation_summary(
        penalty,
        "S001",
        5.00,
        "Visa"
    )

    assert summary["penalty_id"] == "P001"
    assert summary["student_id"] == "S001"
    assert summary["payment_amount"] == 5.00
    assert summary["payment_method"] == "Visa"


def test_s3_06_success_payment_message():
    message = get_user_friendly_payment_message(
        True,
        "Penalty paid successfully.",
        "Visa"
    )

    assert "Penalty paid successfully" in message
    assert "Visa" in message


def test_s3_06_already_paid_error_message():
    message = get_user_friendly_payment_message(
        False,
        "This penalty has already been paid or waived.",
        "Visa"
    )

    assert "Payment failed" in message
    assert "already been paid or waived" in message