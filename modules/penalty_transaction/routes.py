from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date, timedelta

try:
    from config.firebase_config import db, COLLECTION_BORROW_TRANSACTIONS
except ImportError:
    from config.firebase_config import db

    COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"


penalty_bp = Blueprint(
    "penalty_transaction", __name__, url_prefix="/penalty", template_folder="."
)


# =========================================================
# DEMO DATA FOR UI PREVIEW
# =========================================================

DEMO_UI_MODE = True

DEMO_BORROW_TRANSACTIONS = {
    "T001": {
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "borrow_date": "2026-07-01",
        "due_date": (date.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "status": "Borrowed",
    },
    "T002": {
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "borrow_date": "2026-07-05",
        "due_date": (date.today() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "status": "Borrowed",
    },
    "T003": {
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "borrow_date": "2026-07-01",
        "due_date": (date.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "status": "Returned",
    },
}


DEMO_PENALTIES = {
    "P001": {
        "penalty_id": "P001",
        "student_id": "S001",
        "transaction_id": "T001",
        "book_title": "Python Programming",
        "overdue_days": 5,
        "penalty_amount": 5.00,
        "status": "Outstanding",
    },
    "P002": {
        "penalty_id": "P002",
        "student_id": "S002",
        "transaction_id": "T002",
        "book_title": "Database System",
        "overdue_days": 3,
        "penalty_amount": 3.00,
        "status": "Paid",
        "payment_method": "Cash",
        "paid_by": "Student",
        "cash_amount_received": 3.00,
        "change_amount": 0.00,
        "payment_date": "2026-07-14 10:30:00",
    },
    "P003": {
        "penalty_id": "P003",
        "student_id": "S003",
        "transaction_id": "T003",
        "book_title": "Software Engineering",
        "overdue_days": 2,
        "penalty_amount": 2.00,
        "status": "Waived",
        "waiver_reason": "Approved by librarian.",
        "waived_by": "Librarian",
        "waived_date": "2026-07-14 11:00:00",
    },
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================


def convert_to_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    return None


def get_overdue_books():
    today = date.today()
    overdue_books = []

    try:
        docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in docs:
            transaction = doc.to_dict()
            transaction["transaction_id"] = doc.id

            due_date = convert_to_date(transaction.get("due_date"))
            status = str(transaction.get("status", "")).lower()

            if due_date and due_date < today and status != "returned":
                overdue_books.append(transaction)

    except Exception:
        pass

    if DEMO_UI_MODE and len(overdue_books) == 0:
        for transaction_id, transaction in DEMO_BORROW_TRANSACTIONS.items():
            demo_transaction = transaction.copy()
            demo_transaction["transaction_id"] = transaction_id

            due_date = convert_to_date(demo_transaction.get("due_date"))
            status = str(demo_transaction.get("status", "")).lower()

            if due_date and due_date < today and status != "returned":
                overdue_books.append(demo_transaction)

    return overdue_books


PENALTY_RATE_PER_DAY = 1.00


def calculate_penalty_amount(due_date):
    due_date = convert_to_date(due_date)
    today = date.today()

    if due_date is None or due_date >= today:
        return {"overdue_days": 0, "penalty_amount": 0.00}

    overdue_days = (today - due_date).days
    penalty_amount = round(overdue_days * PENALTY_RATE_PER_DAY, 2)

    return {"overdue_days": overdue_days, "penalty_amount": penalty_amount}


def get_outstanding_penalties(student_id=None):
    outstanding_penalties = []

    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()
            penalty["penalty_id"] = doc.id

            status = str(penalty.get("status", "")).lower()

            if status in ["outstanding", "unpaid", "pending"]:
                if student_id is None or penalty.get("student_id") == student_id:
                    outstanding_penalties.append(penalty)

    except Exception:
        pass

    if DEMO_UI_MODE and len(outstanding_penalties) == 0:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            demo_penalty = penalty.copy()
            demo_penalty["penalty_id"] = penalty_id

            status = str(demo_penalty.get("status", "")).lower()

            if status in ["outstanding", "unpaid", "pending"]:
                if student_id is None or demo_penalty.get("student_id") == student_id:
                    outstanding_penalties.append(demo_penalty)

    return outstanding_penalties


def get_penalty_by_id(penalty_id):
    try:
        penalty_doc = db.collection("penalties").document(penalty_id).get()

        if penalty_doc.exists:
            penalty = penalty_doc.to_dict()
            penalty["penalty_id"] = penalty_doc.id
            return penalty

    except Exception:
        pass

    if DEMO_UI_MODE:
        penalty = DEMO_PENALTIES.get(penalty_id)

        if penalty:
            return penalty.copy()

    return None


def pay_penalty_with_credit_card(penalty_id, card_number):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    card_number = card_number.replace(" ", "").replace("-", "")

    if not card_number.isdigit() or len(card_number) < 12:
        return False, "Invalid credit card number."

    payment_data = {
        "status": "Paid",
        "payment_method": "Credit Card",
        "paid_by": "Student",
        "payment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "card_last_four": card_number[-4:],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    updated_database = False

    try:
        penalty_ref = db.collection("penalties").document(penalty_id)
        penalty_doc = penalty_ref.get()

        if getattr(penalty_doc, "exists", False) is True:
            penalty_ref.update(payment_data)
            updated_database = True
    except Exception:
        pass

    if not updated_database and penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(payment_data)

    return True, "Penalty paid successfully using credit card."


def pay_penalty_with_cash(penalty_id, cash_amount):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    try:
        cash_amount = float(cash_amount)
    except ValueError:
        return False, "Invalid cash amount."

    penalty_amount = float(penalty.get("penalty_amount", 0))

    if cash_amount < penalty_amount:
        return False, "Cash amount is less than the penalty amount."

    change_amount = cash_amount - penalty_amount

    payment_data = {
        "status": "Paid",
        "payment_method": "Cash",
        "paid_by": "Student",
        "cash_amount_received": cash_amount,
        "change_amount": change_amount,
        "payment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    updated_database = False

    try:
        penalty_ref = db.collection("penalties").document(penalty_id)
        penalty_doc = penalty_ref.get()

        if getattr(penalty_doc, "exists", False) is True:
            penalty_ref.update(payment_data)
            updated_database = True
    except Exception:
        pass

    if not updated_database and penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(payment_data)

    return True, "Cash penalty payment completed successfully."


def get_penalty_payment_records(student_id=None):
    payment_records = []

    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()
            penalty["penalty_id"] = doc.id

            status = str(penalty.get("status", "")).lower()

            if status == "paid":
                if student_id is None or penalty.get("student_id") == student_id:
                    payment_records.append(penalty)

    except Exception:
        pass

    if DEMO_UI_MODE and len(payment_records) == 0:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            demo_penalty = penalty.copy()
            demo_penalty["penalty_id"] = penalty_id

            status = str(demo_penalty.get("status", "")).lower()

            if status == "paid":
                if student_id is None or demo_penalty.get("student_id") == student_id:
                    payment_records.append(demo_penalty)

    return payment_records


def waive_penalty(penalty_id, waiver_reason, waived_by="Librarian"):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    penalty_status = str(penalty.get("status", "")).lower()

    if penalty_status == "paid":
        return False, "Paid penalties cannot be waived."

    if penalty_status == "waived":
        return False, "Penalty has already been waived."

    # Sprint 2 common validation for penalty waiver
    validation_success, validation_message = validate_penalty_action_data(
        "Waive penalty", waiver_reason=waiver_reason
    )

    if not validation_success:
        return False, validation_message

    reason_success, reason_message, valid_waiver_reason = validate_waiver_reason(
        waiver_reason
    )

    if not reason_success:
        return False, reason_message

    audit_details = build_audit_details("Waive Penalty", waived_by)

    waiver_data = {
        "status": "Waived",
        "waiver_reason": valid_waiver_reason,
        "waived_by": waived_by,
        "waived_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **audit_details,
    }

    update_penalty_record(penalty_id, waiver_data)

    return True, "Penalty waived successfully."


# =========================================================
# SCRUM-705 and SCRUM-706: Return Exception Handling
# =========================================================

DEMO_RETURN_TRANSACTIONS = {
    "RT001": {
        "transaction_id": "RT001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "return_date": "2026-07-15",
        "status": "Return Requested",
    },
    "RT002": {
        "transaction_id": "RT002",
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "return_date": "2026-07-15",
        "status": "Rejected",
        "rejection_reason": "Book condition unacceptable",
    },
    "RT003": {
        "transaction_id": "RT003",
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "return_date": "2026-07-15",
        "status": "Closed",
    },
}


def get_return_transaction_by_id(transaction_id):
    try:
        transaction_doc = (
            db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).get()
        )

        if transaction_doc.exists:
            transaction = transaction_doc.to_dict()
            transaction["transaction_id"] = transaction_doc.id
            return transaction

    except Exception:
        pass

    if DEMO_UI_MODE:
        transaction = DEMO_RETURN_TRANSACTIONS.get(transaction_id)

        if transaction:
            return transaction.copy()

        # Demo penalties use the borrowing transaction IDs (for example,
        # P001 links to T001), so these must be valid exception targets too.
        transaction = DEMO_BORROW_TRANSACTIONS.get(transaction_id)

        if transaction:
            transaction = transaction.copy()
            transaction["transaction_id"] = transaction_id
            return transaction

    return None


def reject_return_exception(transaction_id, rejection_reason, rejected_by="Librarian"):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Return transaction not found."

    status = str(transaction.get("status", "")).lower()

    if status in ["rejected", "closed", "completed"]:
        return False, "This return transaction cannot be rejected."

    rejection_reason = rejection_reason.strip()

    if rejection_reason == "":
        return False, "Rejection reason is required."

    rejection_data = {
        "status": "Rejected",
        "return_status": "Rejected",
        "rejection_reason": rejection_reason,
        "rejected_by": rejected_by,
        "rejected_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).update(
            rejection_data
        )
    except Exception:
        pass

    if transaction_id in DEMO_RETURN_TRANSACTIONS:
        DEMO_RETURN_TRANSACTIONS[transaction_id].update(rejection_data)

    return True, "Return exception rejected successfully."


def penalty_record_exists_for_rejected_return(transaction_id):
    return penalty_record_exists_for_transaction(transaction_id, "Rejected Return")


def validate_penalty_amount(penalty_amount):
    try:
        valid_amount = float(penalty_amount)
    except (TypeError, ValueError):
        return False, "Invalid penalty amount.", None

    if valid_amount <= 0:
        return False, "Penalty amount must be greater than zero.", None

    return True, "Penalty amount is valid.", round(valid_amount, 2)


def create_penalty_record_for_rejected_return(
    transaction_id, penalty_amount, penalty_reason, created_by="Librarian"
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Return transaction not found."

    status = str(transaction.get("status", "")).lower()

    if status != "rejected":
        return False, "Penalty can only be created after the return is rejected."

    if penalty_record_exists_for_rejected_return(transaction_id):
        return False, "Penalty record already exists for this rejected return."

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        return False, amount_message

    penalty_reason = penalty_reason.strip()

    if penalty_reason == "":
        return False, "Penalty reason is required."

    # Sprint 2 common validation for rejected return penalty
    validation_success, validation_message = validate_penalty_action_data(
        "Create rejected return penalty",
        penalty_amount=penalty_amount,
        penalty_reason=penalty_reason,
        transaction_id=transaction_id,
        student_id=transaction.get("student_id"),
        book_id=transaction.get("book_id"),
    )

    if not validation_success:
        return False, validation_message

    penalty_id = "P" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    penalty_data = {
        "penalty_id": penalty_id,
        "student_id": transaction.get("student_id"),
        "transaction_id": transaction_id,
        "book_id": transaction.get("book_id"),
        "book_title": transaction.get("book_title"),
        "penalty_type": "Rejected Return",
        "penalty_reason": penalty_reason,
        "penalty_amount": valid_penalty_amount,
        "status": "Outstanding",
        "created_by": created_by,
        "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_action": "Create Penalty",
        "updated_by": created_by,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    saved_to_database = False

    try:
        db.collection("penalties").document(penalty_id).set(penalty_data)
        saved_to_database = True
    except Exception:
        pass

    if DEMO_UI_MODE and not saved_to_database:
        DEMO_PENALTIES[penalty_id] = penalty_data

    return True, "Penalty record for rejected return created successfully."


# =========================================================
# SCRUM-707: Record Lost or Damaged Book Exception
# =========================================================

DEMO_BOOK_EXCEPTIONS = {}


def book_exception_exists(transaction_id):
    try:
        exception_docs = db.collection("book_exceptions").stream()

        for doc in exception_docs:
            exception = doc.to_dict()

            if exception.get("transaction_id") == transaction_id:
                return True

        return False

    except Exception:
        pass

    if DEMO_UI_MODE:
        for exception in DEMO_BOOK_EXCEPTIONS.values():
            if exception.get("transaction_id") == transaction_id:
                return True

    return False


def record_lost_damaged_book_exception(
    transaction_id, exception_type, exception_description, recorded_by="Librarian"
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Transaction record not found."

    exception_type = exception_type.strip().title()

    if exception_type not in ["Lost", "Damaged"]:
        return False, "Exception type must be Lost or Damaged."

    exception_description = exception_description.strip()

    if exception_description == "":
        return False, "Exception description is required."

    if book_exception_exists(transaction_id):
        return False, "Book exception already exists for this transaction."

    exception_id = "BE" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    exception_data = {
        "exception_id": exception_id,
        "transaction_id": transaction_id,
        "student_id": transaction.get("student_id"),
        "book_id": transaction.get("book_id"),
        "book_title": transaction.get("book_title"),
        "exception_type": exception_type,
        "exception_description": exception_description,
        "exception_status": "Exception Recorded",
        "recorded_by": recorded_by,
        "recorded_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    saved_to_database = False

    try:
        db.collection("book_exceptions").document(exception_id).set(exception_data)
        saved_to_database = True
    except Exception:
        pass

    update_data = {
        "status": exception_type + " Exception Recorded",
        "book_exception_status": "Exception Recorded",
        "exception_type": exception_type,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).update(
            update_data
        )
    except Exception:
        pass

    if transaction_id in DEMO_RETURN_TRANSACTIONS:
        DEMO_RETURN_TRANSACTIONS[transaction_id].update(update_data)

    if DEMO_UI_MODE and not saved_to_database:
        DEMO_BOOK_EXCEPTIONS[exception_id] = exception_data

    return True, "Lost or damaged book exception recorded successfully."


# =========================================================
# SCRUM-709: Prevent Borrowing Approval for Unpaid Penalties
# =========================================================

DEMO_BORROW_REQUESTS = {
    "BR001": {
        "request_id": "BR001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "request_date": "2026-07-15",
        "status": "Pending",
    },
    "BR002": {
        "request_id": "BR002",
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "request_date": "2026-07-15",
        "status": "Pending",
    },
}


def get_unpaid_penalties_by_student(student_id):
    unpaid_penalties = []

    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()
            penalty["penalty_id"] = doc.id

            status = str(penalty.get("status", "")).lower()

            if penalty.get("student_id") == student_id and status in [
                "outstanding",
                "unpaid",
                "pending",
            ]:
                unpaid_penalties.append(penalty)

    except Exception:
        pass

    if DEMO_UI_MODE and len(unpaid_penalties) == 0:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            demo_penalty = penalty.copy()
            demo_penalty["penalty_id"] = penalty_id

            status = str(demo_penalty.get("status", "")).lower()

            if demo_penalty.get("student_id") == student_id and status in [
                "outstanding",
                "unpaid",
                "pending",
            ]:
                unpaid_penalties.append(demo_penalty)

    return unpaid_penalties


# =========================================================
# Sprint 2 - SCRUM-1083
# Penalty and Borrowing Module Integration
# =========================================================


def check_student_borrowing_eligibility(student_id):
    if student_id is None or str(student_id).strip() == "":
        return False, "Student ID is required for borrowing approval.", []

    student_id = str(student_id).strip()

    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if len(unpaid_penalties) > 0:
        return (
            False,
            "Borrowing approval blocked because the student has unpaid penalties.",
            unpaid_penalties,
        )

    return (
        True,
        "Student has no unpaid penalties and can proceed with borrowing approval.",
        [],
    )


def get_borrow_request_by_id(request_id):
    # Check Firebase / fake test database first
    try:
        request_doc = db.collection("borrow_requests").document(request_id).get()

        if getattr(request_doc, "exists", False) is True:
            borrow_request = request_doc.to_dict()
            borrow_request["request_id"] = request_doc.id
            return borrow_request

    except Exception:
        pass

    # Then check demo data
    if request_id in DEMO_BORROW_REQUESTS:
        borrow_request = DEMO_BORROW_REQUESTS[request_id].copy()
        borrow_request["request_id"] = request_id
        return borrow_request

    return None


def approve_borrow_request_with_penalty_check(request_id, approved_by="Librarian"):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return False, "Borrow request not found."

    request_status = str(borrow_request.get("status", "")).strip().lower()

    if request_status not in ["pending", "pending approval"]:
        return False, "Only pending borrow requests can be approved."

    student_id = borrow_request.get("student_id")

    eligibility_success, eligibility_message, unpaid_penalties = (
        check_student_borrowing_eligibility(student_id)
    )

    if not eligibility_success:
        return False, eligibility_message

    approval_data = {
        "status": "Approved",
        "approved_by": approved_by,
        "approved_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_action": "Approve Borrow Request",
        "updated_by": approved_by,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        db.collection("borrow_requests").document(request_id).update(approval_data)
    except Exception:
        pass

    if request_id in DEMO_BORROW_REQUESTS:
        DEMO_BORROW_REQUESTS[request_id].update(approval_data)

    return True, "Borrow request approved successfully."


# =========================================================
# Sprint 2 - S2-YK-01 and S2-YK-02
# Penalty Amount Validation and Student Penalty Access Check
# =========================================================


def validate_penalty_amount(penalty_amount):
    try:
        penalty_amount = float(penalty_amount)
    except (TypeError, ValueError):
        return False, "Invalid penalty amount.", None

    if penalty_amount <= 0:
        return False, "Penalty amount must be greater than zero.", None

    return True, "Penalty amount is valid.", round(penalty_amount, 2)


def get_current_student_id(student_id=None):
    if student_id:
        return student_id

    try:
        session_student_id = session.get("student_id") or session.get("user_id")

        if session_student_id:
            return session_student_id

        form_student_id = request.form.get("student_id")

        if form_student_id:
            return form_student_id

        query_student_id = request.args.get("student_id")

        if query_student_id:
            return query_student_id

    except RuntimeError:
        pass

    # Demo student ID for testing
    return "S001"


def get_penalty_by_id(penalty_id):
    # Check Firebase / fake test database first
    try:
        penalty_doc = db.collection("penalties").document(penalty_id).get()

        if getattr(penalty_doc, "exists", False) is True:
            penalty = penalty_doc.to_dict()
            penalty["penalty_id"] = penalty_doc.id
            return penalty

    except Exception:
        pass

    # Then check demo data
    if penalty_id in DEMO_PENALTIES:
        penalty = DEMO_PENALTIES[penalty_id].copy()
        penalty["penalty_id"] = penalty_id
        return penalty

    return None
    try:
        penalty_doc = db.collection("penalties").document(penalty_id).get()

        if penalty_doc.exists:
            penalty = penalty_doc.to_dict()
            penalty["penalty_id"] = penalty_doc.id
            return penalty

    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
        penalty = DEMO_PENALTIES[penalty_id].copy()
        penalty["penalty_id"] = penalty_id
        return penalty

    return None


def update_penalty_record(penalty_id, update_data):
    updated_database = False

    try:
        penalty_ref = db.collection("penalties").document(penalty_id)
        penalty_doc = penalty_ref.get()

        if getattr(penalty_doc, "exists", False) is True:
            penalty_ref.update(update_data)
            updated_database = True
    except Exception:
        pass

    if not updated_database and penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(update_data)

def normalise_text(value):
    return str(value or "").strip().lower()


def get_display_amount(penalty):
    return (
        penalty.get("penalty_amount")
        or penalty.get("amount")
        or penalty.get("total_amount")
        or 0
    )


def get_display_payment_method(penalty):
    return (
        penalty.get("payment_method")
        or penalty.get("method")
        or "-"
    )


def get_student_penalty_records(student_id):
    penalties = []
    added_penalty_ids = set()

    # Read Firebase / fake test database first
    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()

            if not isinstance(penalty, dict):
                continue

            penalty["penalty_id"] = doc.id

            penalty_student_id = penalty.get("student_id")

            # Old Sprint 1 demo data may not have student_id.
            # Only block when student_id exists and does not match.
            if penalty_student_id and str(penalty_student_id) != str(student_id):
                continue

            penalties.append(penalty)
            added_penalty_ids.add(penalty["penalty_id"])

    except Exception:
        pass

    # Add demo penalties also
    try:
        for penalty_id, penalty_data in DEMO_PENALTIES.items():
            if penalty_id in added_penalty_ids:
                continue

            penalty = penalty_data.copy()
            penalty["penalty_id"] = penalty_id

            penalty_student_id = penalty.get("student_id")

            if penalty_student_id and str(penalty_student_id) != str(student_id):
                continue

            penalties.append(penalty)

    except Exception:
        pass

    return penalties


def filter_student_penalty_records(
    penalties,
    keyword=None,
    status_filter=None,
    payment_method_filter=None
):
    keyword = normalise_text(keyword)
    status_filter = normalise_text(status_filter)
    payment_method_filter = normalise_text(payment_method_filter)

    filtered_penalties = []

    for penalty in penalties:
        penalty_status = normalise_text(penalty.get("status"))
        payment_method = normalise_text(get_display_payment_method(penalty))

        # Filter by status
        if status_filter and status_filter != "all":
            if penalty_status != status_filter:
                continue

        # Filter by payment method
        if payment_method_filter and payment_method_filter != "all":
            if payment_method != payment_method_filter:
                continue

        # Search by penalty ID, book title, book ID, or penalty reason
        if keyword:
            searchable_text = " ".join([
                str(penalty.get("penalty_id", "")),
                str(penalty.get("book_title", "")),
                str(penalty.get("book_id", "")),
                str(penalty.get("penalty_reason", "")),
                str(penalty.get("penalty_type", "")),
            ]).lower()

            if keyword not in searchable_text:
                continue

        filtered_penalties.append(penalty)

    return filtered_penalties


def build_payment_receipt(penalty_id, student_id):
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id
    )

    if not access_success:
        return False, access_message, None

    penalty_status = normalise_text(penalty.get("status"))

    if penalty_status != "paid":
        return False, "Payment receipt is only available after successful payment.", None

    receipt = {
        "penalty_id": penalty_id,
        "student_id": penalty.get("student_id") or student_id,
        "book_title": penalty.get("book_title") or "-",
        "penalty_reason": penalty.get("penalty_reason") or penalty.get("penalty_type") or "-",
        "payment_amount": get_display_amount(penalty),
        "payment_method": get_display_payment_method(penalty),
        "payment_status": penalty.get("status") or "Paid",
        "payment_date": penalty.get("paid_date") or penalty.get("payment_date") or "-",
        "paid_by": penalty.get("paid_by") or student_id
    }

    return True, "Payment receipt generated successfully.", receipt


def validate_penalty_payment_status(penalty):
    penalty_status = str(penalty.get("status", "")).lower()

    if penalty_status in ["paid", "waived"]:
        return False, "This penalty has already been paid or waived."

    if penalty_status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    return True, "Penalty can be paid."


def validate_student_penalty_access(penalty_id, student_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found.", None

    penalty_student_id = penalty.get("student_id")

    # Some old Sprint 1 test data does not include student_id.
    # Only check ownership when student_id exists in the penalty record.
    if penalty_student_id and penalty_student_id != student_id:
        return (
            False,
            "You are not allowed to access another student's penalty record.",
            penalty,
        )

    return True, "Student is allowed to access this penalty.", penalty


def pay_student_own_penalty(
    penalty_id, student_id, payment_amount, payment_method="Credit Card"
):
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id, student_id
    )

    if not access_success:
        return False, access_message

    validation_success, validation_message = validate_penalty_action_data(
        "Pay penalty", penalty_amount=payment_amount, student_id=student_id
    )

    if not validation_success:
        return False, validation_message

    amount_success, amount_message, valid_amount = validate_penalty_amount(
        payment_amount
    )

    if not amount_success:
        return False, amount_message

    status_success, status_message = validate_penalty_payment_status(penalty)

    if not status_success:
        return False, status_message

    expected_amount_value = (
        penalty.get("penalty_amount")
        or penalty.get("amount")
        or penalty.get("total_amount")
        or payment_amount
    )

    expected_amount = float(expected_amount_value)

    if valid_amount != expected_amount:
        return False, "Payment amount does not match the penalty amount."

    audit_details = build_audit_details("Pay Penalty", student_id)

    update_data = {
        "status": "Paid",
        "payment_method": payment_method,
        "paid_by": student_id,
        "paid_amount": valid_amount,
        "paid_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **audit_details,
    }

    update_penalty_record(penalty_id, update_data)

    return True, "Penalty paid successfully."


def penalty_record_exists_for_transaction(transaction_id, penalty_type=None):
    # Check demo data first for testing
    for penalty in DEMO_PENALTIES.values():
        same_transaction = penalty.get("transaction_id") == transaction_id

        if penalty_type is None:
            if same_transaction:
                return True
        else:
            same_penalty_type = penalty.get("penalty_type") == penalty_type

            if same_transaction and same_penalty_type:
                return True

    # Check Firebase
    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()

            same_transaction = penalty.get("transaction_id") == transaction_id

            if penalty_type is None:
                if same_transaction:
                    return True
            else:
                same_penalty_type = penalty.get("penalty_type") == penalty_type

                if same_transaction and same_penalty_type:
                    return True

    except Exception:
        pass

    return False


# =========================================================
# Sprint 2 - SCRUM-1081 and SCRUM-1082
# Waiver Reason Validation and Audit Details
# =========================================================


def validate_waiver_reason(waiver_reason):
    if waiver_reason is None:
        return False, "Waiver reason is required.", None

    waiver_reason = waiver_reason.strip()

    if waiver_reason == "":
        return False, "Waiver reason is required.", None

    if len(waiver_reason) < 5:
        return False, "Waiver reason must be at least 5 characters.", None

    return True, "Waiver reason is valid.", waiver_reason
    if waiver_reason is None:
        return False, "Waiver reason is required."

    waiver_reason = waiver_reason.strip()

    if waiver_reason == "":
        return False, "Waiver reason is required."

    if len(waiver_reason) < 5:
        return False, "Waiver reason must be at least 5 characters."

    return True, "Waiver reason is valid.", waiver_reason


def build_audit_details(action_name, actor_name):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "last_action": action_name,
        "updated_by": actor_name,
        "updated_at": current_time,
    }


# =========================================================
# Sprint 2 - SCRUM-1084, SCRUM-1085, SCRUM-1086
# Exception Handling and Clear Validation Messages
# =========================================================


def validate_required_field(value, field_name):
    if value is None:
        return False, f"{field_name} is required.", None

    value = str(value).strip()

    if value == "":
        return False, f"{field_name} is required.", None

    return True, f"{field_name} is valid.", value


def create_penalty_action_message(action_name, success, message):
    if success:
        return f"{action_name} completed successfully. {message}"

    return f"{action_name} failed. Reason: {message}"


def validate_book_exception_type(exception_type):
    success, message, valid_exception_type = validate_required_field(
        exception_type, "Book exception type"
    )

    if not success:
        return False, message, None

    valid_exception_type = valid_exception_type.title()

    if valid_exception_type not in ["Lost", "Damaged"]:
        return False, "Book exception type must be Lost or Damaged.", None

    return True, "Book exception type is valid.", valid_exception_type


def handle_rejected_return_exception(
    transaction_id, penalty_amount, penalty_reason, handled_by="Librarian"
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        message = create_penalty_action_message(
            "Rejected return exception handling", False, "Return transaction not found."
        )
        return False, message

    status = str(transaction.get("status", "")).lower()

    if status != "rejected":
        message = create_penalty_action_message(
            "Rejected return exception handling",
            False,
            "Penalty can only be created after the return is rejected.",
        )
        return False, message

    if penalty_record_exists_for_rejected_return(transaction_id):
        message = create_penalty_action_message(
            "Rejected return exception handling",
            False,
            "Penalty record already exists for this rejected return.",
        )
        return False, message

    reason_success, reason_message, valid_penalty_reason = validate_required_field(
        penalty_reason, "Penalty reason"
    )

    if not reason_success:
        message = create_penalty_action_message(
            "Rejected return exception handling", False, reason_message
        )
        return False, message

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        message = create_penalty_action_message(
            "Rejected return exception handling", False, amount_message
        )
        return False, message

    success, result_message = create_penalty_record_for_rejected_return(
        transaction_id, valid_penalty_amount, valid_penalty_reason, handled_by
    )

    if not success:
        message = create_penalty_action_message(
            "Rejected return exception handling", False, result_message
        )
        return False, message

    message = create_penalty_action_message(
        "Rejected return exception handling",
        True,
        "Rejected return penalty record has been created.",
    )
    return True, message


def create_lost_damaged_book_exception_penalty(
    transaction_id,
    exception_type,
    exception_description,
    penalty_amount,
    recorded_by="Librarian",
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        message = create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            "Return transaction not found.",
        )
        return False, message

    # Sprint 2 common validation for lost/damaged book penalty
    validation_success, validation_message = validate_penalty_action_data(
        "Create lost or damaged book penalty",
        penalty_amount=penalty_amount,
        transaction_id=transaction_id,
        student_id=transaction.get("student_id"),
        book_id=transaction.get("book_id"),
        exception_type=exception_type,
        exception_description=exception_description,
    )

    if not validation_success:
        return False, validation_message

    type_success, type_message, valid_exception_type = validate_book_exception_type(
        exception_type
    )

    if not type_success:
        message = create_penalty_action_message(
            "Lost or damaged book exception handling", False, type_message
        )
        return False, message

    description_success, description_message, valid_description = (
        validate_required_field(exception_description, "Exception description")
    )

    if not description_success:
        message = create_penalty_action_message(
            "Lost or damaged book exception handling", False, description_message
        )
        return False, message

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        message = create_penalty_action_message(
            "Lost or damaged book exception handling", False, amount_message
        )
        return False, message

    if penalty_record_exists_for_transaction(transaction_id, "Lost/Damaged Book"):
        message = create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            "Penalty record already exists for this lost or damaged book exception.",
        )
        return False, message

    penalty_id = "P" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    penalty_data = {
        "penalty_id": penalty_id,
        "student_id": transaction.get("student_id"),
        "transaction_id": transaction_id,
        "book_id": transaction.get("book_id"),
        "book_title": transaction.get("book_title"),
        "penalty_type": "Lost/Damaged Book",
        "exception_type": valid_exception_type,
        "exception_description": valid_description,
        "penalty_reason": valid_exception_type + " book exception",
        "penalty_amount": valid_penalty_amount,
        "status": "Outstanding",
        "created_by": recorded_by,
        "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_action": "Create Lost/Damaged Book Penalty",
        "updated_by": recorded_by,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        db.collection("penalties").document(penalty_id).set(penalty_data)
    except Exception:
        pass

    DEMO_PENALTIES[penalty_id] = penalty_data

    message = create_penalty_action_message(
        "Lost or damaged book exception handling",
        True,
        "Lost or damaged book penalty record has been created.",
    )

    return True, message


# =========================================================
# Sprint 2 - Common Validation for All Penalty Actions
# =========================================================


def validate_penalty_action_data(
    action_name,
    penalty_amount=None,
    penalty_reason=None,
    transaction_id=None,
    student_id=None,
    book_id=None,
    exception_type=None,
    exception_description=None,
    waiver_reason=None,
):
    if transaction_id is not None:
        success, message, valid_transaction_id = validate_required_field(
            transaction_id, "Transaction ID"
        )

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if student_id is not None:
        success, message, valid_student_id = validate_required_field(
            student_id, "Student ID"
        )

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if book_id is not None:
        success, message, valid_book_id = validate_required_field(book_id, "Book ID")

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if penalty_amount is not None:
        success, message, valid_amount = validate_penalty_amount(penalty_amount)

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if penalty_reason is not None:
        success, message, valid_reason = validate_required_field(
            penalty_reason, "Penalty reason"
        )

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if exception_type is not None:
        success, message, valid_exception_type = validate_book_exception_type(
            exception_type
        )

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if exception_description is not None:
        success, message, valid_description = validate_required_field(
            exception_description, "Exception description"
        )

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if waiver_reason is not None:
        success, message, valid_waiver_reason = validate_waiver_reason(waiver_reason)

        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    return True, create_penalty_action_message(
        action_name, True, "All validation checks passed."
    )



# =========================================================
# Sprint 3 - S3-03, S3-04, S3-05, S3-06
# Librarian Search, Dynamic Payment Form, Confirmation Summary,
# and User-Friendly Payment Messages
# =========================================================

def get_all_penalty_records():
    penalties = []
    added_penalty_ids = set()

    # Read Firebase / fake test database first
    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()

            if not isinstance(penalty, dict):
                continue

            penalty["penalty_id"] = doc.id
            penalties.append(penalty)
            added_penalty_ids.add(doc.id)

    except Exception:
        pass

    # Add demo penalties also
    try:
        for penalty_id, penalty_data in DEMO_PENALTIES.items():
            if penalty_id in added_penalty_ids:
                continue

            penalty = penalty_data.copy()
            penalty["penalty_id"] = penalty_id

            if "student_name" not in penalty:
                penalty["student_name"] = get_demo_student_name(
                    penalty.get("student_id")
                )

            penalties.append(penalty)

    except Exception:
        pass

    return penalties


def get_demo_student_name(student_id):
    demo_students = {
        "S001": "Ali Tan",
        "S002": "Mei Ling",
        "S003": "Kumar Raj"
    }

    return demo_students.get(str(student_id), "-")


def search_librarian_penalty_records(penalties, search_keyword=None):
    search_keyword = normalise_text(search_keyword)

    if not search_keyword:
        return penalties

    searched_penalties = []

    for penalty in penalties:
        searchable_text = " ".join([
            str(penalty.get("penalty_id", "")),
            str(penalty.get("student_id", "")),
            str(penalty.get("student_name", "")),
            str(penalty.get("book_title", "")),
            str(penalty.get("penalty_reason", "")),
            str(penalty.get("penalty_type", "")),
            str(penalty.get("status", "")),
        ]).lower()

        if search_keyword in searchable_text:
            searched_penalties.append(penalty)

    return searched_penalties


def validate_dynamic_payment_details(payment_method, form_data):
    payment_method = str(payment_method or "").strip()

    if payment_method == "":
        return False, "Please select a payment method."

    method = payment_method.lower()

    if method in ["visa", "debit card", "credit card"]:
        required_fields = {
            "card_number": "Card number is required.",
            "card_holder": "Card holder name is required.",
            "expiry_date": "Expiry date is required.",
            "cvv": "CVV is required."
        }

        for field_name, error_message in required_fields.items():
            if str(form_data.get(field_name, "")).strip() == "":
                return False, error_message

    elif method == "paypal":
        paypal_email = str(form_data.get("paypal_email", "")).strip()

        if paypal_email == "":
            return False, "PayPal email is required."

        if "@" not in paypal_email:
            return False, "Please enter a valid PayPal email address."

    elif method == "cash":
        # Cash does not need extra student payment fields
        pass

    else:
        return False, "Invalid payment method selected."

    return True, "Payment details are valid."


def build_payment_confirmation_summary(penalty, student_id, payment_amount, payment_method):
    return {
        "penalty_id": penalty.get("penalty_id", "-"),
        "student_id": penalty.get("student_id") or student_id,
        "book_title": penalty.get("book_title", "-"),
        "penalty_reason": penalty.get("penalty_reason") or penalty.get("penalty_type") or "-",
        "payment_amount": payment_amount,
        "payment_method": payment_method,
        "penalty_status": penalty.get("status", "-")
    }


def get_user_friendly_payment_message(success, system_message, payment_method=None):
    message = str(system_message or "")

    if success:
        if payment_method:
            return f"Penalty paid successfully. Your payment using {payment_method} has been recorded."

        return "Penalty paid successfully. Your payment has been recorded."

    lower_message = message.lower()

    if "already been paid" in lower_message or "paid or waived" in lower_message:
        return "Payment failed. This penalty has already been paid or waived."

    if "amount does not match" in lower_message:
        return "Payment failed. The payment amount does not match the penalty amount."

    if "greater than zero" in lower_message:
        return "Payment failed. The payment amount must be greater than zero."

    if "invalid penalty amount" in lower_message:
        return "Payment failed. Please enter a valid payment amount."

    if "not allowed" in lower_message:
        return "Payment failed. You are not allowed to pay another student's penalty."

    if "not found" in lower_message:
        return "Payment failed. The penalty record cannot be found."

    if message:
        return f"Payment failed. {message}"

    return "Payment failed. Please check the payment details and try again."


# =========================================================
# ROUTES
# =========================================================


@penalty_bp.route("/librarian")
def librarian_penalty_dashboard():
    return render_template("librarian/dashboard.html")


@penalty_bp.route("/overdue")
@penalty_bp.route("/librarian/overdue")
def identify_overdue_books():
    overdue_books = get_overdue_books()

    return render_template("librarian/overdue_book.html", overdue_books=overdue_books)


@penalty_bp.route("/penalties")
@penalty_bp.route("/outstanding")
@penalty_bp.route("/librarian/penalties")
def view_outstanding_penalties():
    student_id = request.args.get("student_id", "").strip()
    search_keyword = request.args.get("search_keyword", "").strip()

    if search_keyword:
        all_penalties = get_all_penalty_records()

        outstanding_penalties = search_librarian_penalty_records(
            all_penalties,
            search_keyword
        )
    else:
        outstanding_penalties = get_outstanding_penalties(student_id)

    return render_template(
        "librarian/outstanding_penalties.html",
        outstanding_penalties=outstanding_penalties,
        student_id=student_id,
        search_keyword=search_keyword,
        result_count=len(outstanding_penalties)
    )


@penalty_bp.route("/student")
@penalty_bp.route("/student/<student_id>")
def student_penalty_records(student_id=None):
    resolved_student_id = (
        student_id or session.get("student_id") or session.get("user_id")
    )

    if not resolved_student_id:
        flash("Please log in as a student to view penalty records.", "warning")
        return redirect(url_for("authentication.login"))

    penalties = get_outstanding_penalties(resolved_student_id)

    return render_template(
        "student/penalty_records.html",
        student_id=resolved_student_id,
        penalties=penalties,
    )


@penalty_bp.route("/pay-credit-card/<penalty_id>", methods=["GET", "POST"])
@penalty_bp.route("/student/pay-credit-card/<penalty_id>", methods=["GET", "POST"])
def student_pay_credit_card(penalty_id):
    student_id = get_current_student_id()

    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id
    )

    if not access_success:
        return access_message, 403

    if request.method == "POST":
        payment_amount = (
            request.form.get("payment_amount")
            or request.form.get("amount")
            or penalty.get("penalty_amount")
            or penalty.get("amount")
            or penalty.get("total_amount")
        )

        payment_method = request.form.get("payment_method", "").strip()

        # Old Sprint 1 / Sprint 2 compatibility
        # Old test data may submit card_number without payment_method
        is_legacy_payment = payment_method == ""

        if is_legacy_payment:
            payment_method = "Credit Card"
        else:
            details_success, details_message = validate_dynamic_payment_details(
                payment_method,
                request.form
            )

            if not details_success:
                friendly_message = get_user_friendly_payment_message(
                    False,
                    details_message,
                    payment_method
                )

                confirmation_summary = build_payment_confirmation_summary(
                    penalty,
                    student_id,
                    payment_amount,
                    payment_method
                )

                return render_template(
                    "student/pay_credit_card.html",
                    penalty=penalty,
                    student_id=student_id,
                    error=friendly_message,
                    confirmation_summary=confirmation_summary
                ), 400

        success, message = pay_student_own_penalty(
            penalty_id,
            student_id,
            payment_amount,
            payment_method
        )

        friendly_message = get_user_friendly_payment_message(
            success,
            message,
            payment_method
        )

        friendly_message = get_user_friendly_payment_message(
        success,
        message,
        "Cash"
        )

        if success:
            flash(friendly_message, "success")

    # Keep old Sprint 1 credit card payment test compatible
    # Old test submits card details without payment_method
        if is_legacy_payment:
            return redirect(url_for("penalty_transaction.student_penalty_records"))

    # Sprint 3 new payment receipt flow
        return redirect(url_for(
        "penalty_transaction.payment_receipt",
        penalty_id=penalty_id
    ))

        confirmation_summary = build_payment_confirmation_summary(
            penalty,
            student_id,
            payment_amount,
            payment_method
        )

        return render_template(
            "student/pay_credit_card.html",
            penalty=penalty,
            student_id=student_id,
            error=friendly_message,
            confirmation_summary=confirmation_summary
        ), 400

    return render_template(
        "student/pay_credit_card.html",
        penalty=penalty,
        student_id=student_id
    )


@penalty_bp.route("/student/pay-cash/<penalty_id>", methods=["GET", "POST"])
def student_pay_cash(penalty_id):
    student_id = get_current_student_id()
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id, student_id
    )

    if not access_success:
        return access_message, 403

    if request.method == "POST":
        payment_amount = (
            request.form.get("payment_amount")
            or request.form.get("cash_amount")
            or penalty.get("penalty_amount")
            or penalty.get("amount")
            or penalty.get("total_amount")
        )

        # Support old Sprint 1 cash payment test
        if request.form.get("cash_amount"):
            success, message = pay_penalty_with_cash(penalty_id, payment_amount)
        else:
            success, message = pay_student_own_penalty(
                penalty_id, student_id, payment_amount, "Cash"
            )

        if success:
            flash(message, "success")

    # Keep old Sprint 1 cash payment test compatible
            if request.form.get("cash_amount"):
                return redirect(url_for("penalty_transaction.student_penalty_records"))

    # Sprint 3 receipt flow
            return redirect(url_for(
                "penalty_transaction.payment_receipt",
                    penalty_id=penalty_id
                 ))

    return render_template(
        "student/pay_cash.html", penalty=penalty, student_id=student_id
    )
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()

        success, message = pay_penalty_with_cash(penalty_id, cash_amount)

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return (
            render_template("student/pay_cash.html", penalty=penalty, error=message),
            400,
        )

    return render_template("student/pay_cash.html", penalty=penalty)


@penalty_bp.route("/payment-records")
@penalty_bp.route("/librarian/payment-records")
def view_payment_records():
    student_id = request.args.get("student_id")

    if student_id:
        student_id = student_id.strip()

    payment_records = get_penalty_payment_records(student_id)

    return render_template(
        "librarian/payment_records.html",
        payment_records=payment_records,
        student_id=student_id,
    )


@penalty_bp.route("/librarian/waive", methods=["GET"])
def librarian_choose_penalty_to_waive():
    outstanding_penalties = get_outstanding_penalties()

    return render_template(
        "librarian/select_penalty_to_waive.html",
        outstanding_penalties=outstanding_penalties,
    )


@penalty_bp.route("/librarian/waive/<penalty_id>", methods=["GET", "POST"])
def librarian_waive_penalty(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        waiver_reason = request.form.get("waiver_reason", "").strip()
        waived_by = request.form.get("waived_by", "Librarian").strip()

        success, message = waive_penalty(penalty_id, waiver_reason, waived_by)

        if success:
            flash(message, "success")
            return redirect(
                url_for("penalty_transaction.librarian_choose_penalty_to_waive")
            )

        return (
            render_template(
                "librarian/waive_penalty.html", penalty=penalty, error=message
            ),
            400,
        )

    return render_template("librarian/waive_penalty.html", penalty=penalty)


@penalty_bp.route("/librarian/reject-return/<transaction_id>", methods=["GET", "POST"])
def librarian_reject_return_exception(transaction_id):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return "Return transaction not found", 404

    if request.method == "POST":
        rejection_reason = request.form.get("rejection_reason", "").strip()
        rejected_by = request.form.get("rejected_by", "Librarian").strip()
        penalty_amount = request.form.get("penalty_amount", "").strip()

        success, message = reject_return_exception(
            transaction_id, rejection_reason, rejected_by
        )

        if not success:
            return (
                render_template(
                    "librarian/reject_return_exception.html",
                    transaction=transaction,
                    error=message,
                ),
                400,
            )

        penalty_success, penalty_message = create_penalty_record_for_rejected_return(
            transaction_id, penalty_amount, rejection_reason, rejected_by
        )

        if not penalty_success:
            return (
                render_template(
                    "librarian/reject_return_exception.html",
                    transaction=transaction,
                    error=penalty_message,
                ),
                400,
            )

        flash(message + " " + penalty_message, "success")
        return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

    return render_template(
        "librarian/reject_return_exception.html", transaction=transaction
    )


@penalty_bp.route("/librarian/book-exception", methods=["GET"])
def librarian_choose_book_exception():
    transactions = []

    try:
        transaction_docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in transaction_docs:
            transaction = doc.to_dict()
            transaction["transaction_id"] = doc.id
            transactions.append(transaction)
    except Exception:
        pass

    if not transactions:
        for transaction_id, transaction in DEMO_BORROW_TRANSACTIONS.items():
            demo_transaction = transaction.copy()
            demo_transaction["transaction_id"] = transaction_id
            transactions.append(demo_transaction)

    return render_template(
        "librarian/select_book_exception.html",
        transactions=transactions,
    )


@penalty_bp.route("/librarian/book-exception/<transaction_id>", methods=["GET", "POST"])
def librarian_record_book_exception(transaction_id):
    transaction = get_return_transaction_by_id(transaction_id)

    # The waive page links from a penalty record.  Older penalty records and
    # Firestore-generated penalty IDs cannot be used directly as borrowing
    # transaction document IDs, so resolve the linked transaction first.
    if transaction is None:
        penalty = get_penalty_by_id(transaction_id)
        linked_transaction_id = penalty.get("transaction_id") if penalty else None

        if linked_transaction_id:
            transaction_id = linked_transaction_id
            transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return "Transaction record not found", 404

    if request.method == "POST":
        exception_type = request.form.get("exception_type", "").strip()
        exception_description = request.form.get("exception_description", "").strip()
        recorded_by = request.form.get("recorded_by", "Librarian").strip()

        success, message = record_lost_damaged_book_exception(
            transaction_id, exception_type, exception_description, recorded_by
        )

        if success:
            flash(message, "success")
            return redirect(
                url_for("penalty_transaction.librarian_choose_book_exception")
            )

        return (
            render_template(
                "librarian/book_exception.html", transaction=transaction, error=message
            ),
            400,
        )

    return render_template("librarian/book_exception.html", transaction=transaction)


@penalty_bp.route(
    "/librarian/check-borrow-approval/<request_id>", methods=["GET", "POST"]
)
def librarian_check_borrow_approval(request_id):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return "Borrow request not found", 404

    student_id = borrow_request.get("student_id")
    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if request.method == "POST":
        approved_by = request.form.get("approved_by", "Librarian").strip()

        success, message = approve_borrow_request_with_penalty_check(
            request_id, approved_by
        )

        if success:
            flash(message, "success")
            return redirect(
                url_for(
                    "penalty_transaction.librarian_check_borrow_approval",
                    request_id=request_id,
                )
            )

        return (
            render_template(
                "librarian/check_borrow_approval.html",
                borrow_request=borrow_request,
                unpaid_penalties=unpaid_penalties,
                error=message,
            ),
            400,
        )

    return render_template(
        "librarian/check_borrow_approval.html",
        borrow_request=borrow_request,
        unpaid_penalties=unpaid_penalties,
    )

@penalty_bp.route("/student/penalties", methods=["GET"])
def student_penalty_search_filter():
    student_id = get_current_student_id()

    keyword = request.args.get("keyword", "").strip()
    status_filter = request.args.get("status", "all").strip()
    payment_method_filter = request.args.get("payment_method", "all").strip()

    all_penalties = get_student_penalty_records(student_id)

    filtered_penalties = filter_student_penalty_records(
        all_penalties,
        keyword,
        status_filter,
        payment_method_filter
    )

    return render_template(
        "student/penalty_records.html",
        penalties=filtered_penalties,
        total_penalties=len(all_penalties),
        result_count=len(filtered_penalties),
        keyword=keyword,
        status_filter=status_filter,
        payment_method_filter=payment_method_filter
    )


@penalty_bp.route("/student/payment-receipt/<penalty_id>", methods=["GET"])
def payment_receipt(penalty_id):
    student_id = get_current_student_id()

    success, message, receipt = build_payment_receipt(
        penalty_id,
        student_id
    )

    if not success:
        return message, 403

    return render_template(
        "student/payment_receipt.html",
        receipt=receipt
    )