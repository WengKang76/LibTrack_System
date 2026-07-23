from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date, timedelta

try:
    from config.firebase_config import db, COLLECTION_BORROW_TRANSACTIONS
except ImportError:
    from config.firebase_config import db
    COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"


penalty_bp = Blueprint(
    "penalty_transaction",
    __name__,
    url_prefix="/penalty",
    template_folder="."
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
        "status": "Borrowed"
    },
    "T002": {
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "borrow_date": "2026-07-05",
        "due_date": (date.today() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "status": "Borrowed"
    },
    "T003": {
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "borrow_date": "2026-07-01",
        "due_date": (date.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "status": "Returned"
    }
}


DEMO_PENALTIES = {
    "P001": {
        "penalty_id": "P001",
        "student_id": "S001",
        "transaction_id": "T001",
        "book_title": "Python Programming",
        "overdue_days": 5,
        "penalty_amount": 5.00,
        "status": "Outstanding"
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
        "payment_date": "2026-07-14 10:30:00"
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
        "waived_date": "2026-07-14 11:00:00"
    }
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
        return {
            "overdue_days": 0,
            "penalty_amount": 0.00
        }

    overdue_days = (today - due_date).days
    penalty_amount = overdue_days * PENALTY_RATE_PER_DAY

    return {
        "overdue_days": overdue_days,
        "penalty_amount": penalty_amount
    }


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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(payment_data)
    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(payment_data)
    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
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

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be waived."

    waiver_reason = waiver_reason.strip()

    if waiver_reason == "":
        return False, "Waiver reason is required."

    waiver_data = {
        "status": "Waived",
        "waiver_reason": waiver_reason,
        "waived_by": waived_by,
        "waived_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(waiver_data)
    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(waiver_data)

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
        "status": "Return Requested"
    },
    "RT002": {
        "transaction_id": "RT002",
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "return_date": "2026-07-15",
        "status": "Rejected",
        "rejection_reason": "Book condition unacceptable"
    },
    "RT003": {
        "transaction_id": "RT003",
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "return_date": "2026-07-15",
        "status": "Closed"
    }
}


def get_return_transaction_by_id(transaction_id):
    try:
        transaction_doc = db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).get()

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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).update(rejection_data)
    except Exception:
        pass

    if transaction_id in DEMO_RETURN_TRANSACTIONS:
        DEMO_RETURN_TRANSACTIONS[transaction_id].update(rejection_data)

    return True, "Return exception rejected successfully."


def penalty_record_exists_for_rejected_return(transaction_id):
    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()

            if (
                penalty.get("transaction_id") == transaction_id
                and penalty.get("penalty_type") == "Rejected Return"
            ):
                return True

        return False

    except Exception:
        pass

    if DEMO_UI_MODE:
        for penalty in DEMO_PENALTIES.values():
            if (
                penalty.get("transaction_id") == transaction_id
                and penalty.get("penalty_type") == "Rejected Return"
            ):
                return True

    return False
    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()

            if (
                penalty.get("transaction_id") == transaction_id
                and penalty.get("penalty_type") == "Rejected Return"
            ):
                return True

    except Exception:
        pass

    if DEMO_UI_MODE:
        for penalty in DEMO_PENALTIES.values():
            if (
                penalty.get("transaction_id") == transaction_id
                and penalty.get("penalty_type") == "Rejected Return"
            ):
                return True

    return False

def validate_penalty_amount(penalty_amount):
    try:
        valid_amount = float(penalty_amount)
    except (TypeError, ValueError):
        return False, "Invalid penalty amount.", None

    if valid_amount <= 0:
        return False, "Penalty amount must be greater than zero.", None

    return True, "Penalty amount is valid.", round(valid_amount, 2)


def create_penalty_record_for_rejected_return(
    transaction_id,
    penalty_amount,
    penalty_reason,
    created_by="Librarian"
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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    transaction_id,
    exception_type,
    exception_description,
    recorded_by="Librarian"
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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).update(update_data)
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
        "status": "Pending"
    },
    "BR002": {
        "request_id": "BR002",
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "request_date": "2026-07-15",
        "status": "Pending"
    }
}


def get_unpaid_penalties_by_student(student_id):
    unpaid_penalties = []

    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()
            penalty["penalty_id"] = doc.id

            status = str(penalty.get("status", "")).lower()

            if (
                penalty.get("student_id") == student_id
                and status in ["outstanding", "unpaid", "pending"]
            ):
                unpaid_penalties.append(penalty)

    except Exception:
        pass

    if DEMO_UI_MODE and len(unpaid_penalties) == 0:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            demo_penalty = penalty.copy()
            demo_penalty["penalty_id"] = penalty_id

            status = str(demo_penalty.get("status", "")).lower()

            if (
                demo_penalty.get("student_id") == student_id
                and status in ["outstanding", "unpaid", "pending"]
            ):
                unpaid_penalties.append(demo_penalty)

    return unpaid_penalties


def get_borrow_request_by_id(request_id):
    try:
        request_doc = db.collection("borrow_requests").document(request_id).get()

        if request_doc.exists:
            borrow_request = request_doc.to_dict()
            borrow_request["request_id"] = request_doc.id
            return borrow_request

    except Exception:
        pass

    if DEMO_UI_MODE:
        borrow_request = DEMO_BORROW_REQUESTS.get(request_id)

        if borrow_request:
            return borrow_request.copy()

    return None


def approve_borrow_request_with_penalty_check(request_id, approved_by="Librarian"):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return False, "Borrow request not found."

    request_status = str(borrow_request.get("status", "")).lower()

    if request_status != "pending":
        return False, "Only pending borrow requests can be approved."

    student_id = borrow_request.get("student_id")
    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if len(unpaid_penalties) > 0:
        return False, "Borrowing approval blocked because the student has unpaid penalties."

    approval_data = {
        "status": "Approved",
        "approved_by": approved_by,
        "approved_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        session_student_id = session.get("student_id")

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
    # During testing/demo, check demo data first
    if penalty_id in DEMO_PENALTIES:
        penalty = DEMO_PENALTIES[penalty_id].copy()
        penalty["penalty_id"] = penalty_id
        return penalty

    # Then check Firebase if demo data does not have it
    try:
        penalty_doc = db.collection("penalties").document(penalty_id).get()

        if penalty_doc.exists:
            penalty = penalty_doc.to_dict()
            penalty["penalty_id"] = penalty_doc.id
            return penalty

    except Exception:
        pass

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
    try:
        db.collection("penalties").document(penalty_id).update(update_data)
    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(update_data)


def validate_student_penalty_access(penalty_id, student_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found.", None

    if penalty.get("student_id") != student_id:
        return False, "You are not allowed to access another student's penalty record.", penalty

    return True, "Student is allowed to access this penalty.", penalty


def pay_student_own_penalty(
    penalty_id,
    student_id,
    payment_amount,
    payment_method="Credit Card"
):
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id
    )

    if not access_success:
        return False, access_message

    amount_success, amount_message, valid_amount = validate_penalty_amount(
        payment_amount
    )

    if not amount_success:
        return False, amount_message

    penalty_status = str(penalty.get("status", "")).lower()

    if penalty_status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    expected_amount = float(penalty.get("penalty_amount", 0))

    if valid_amount != expected_amount:
        return False, "Payment amount does not match the penalty amount."

    update_data = {
        "status": "Paid",
        "payment_method": payment_method,
        "paid_by": student_id,
        "paid_amount": valid_amount,
        "paid_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    update_penalty_record(penalty_id, update_data)

    return True, "Penalty paid successfully."

# =========================================================
# ROUTES
# =========================================================

@penalty_bp.route("/overdue")
@penalty_bp.route("/librarian/overdue")
def identify_overdue_books():
    overdue_books = get_overdue_books()

    return render_template(
        "librarian/overdue_book.html",
        overdue_books=overdue_books
    )


@penalty_bp.route("/penalties")
@penalty_bp.route("/outstanding")
@penalty_bp.route("/librarian/penalties")
def view_outstanding_penalties():
    student_id = request.args.get("student_id")

    if student_id:
        student_id = student_id.strip()

    outstanding_penalties = get_outstanding_penalties(student_id)

    return render_template(
        "librarian/outstanding_penalties.html",
        outstanding_penalties=outstanding_penalties,
        student_id=student_id
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
        )

        success, message = pay_student_own_penalty(
            penalty_id,
            student_id,
            payment_amount,
            "Credit Card"
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_credit_card.html",
            penalty=penalty,
            student_id=student_id,
            error=message
        ), 400

    return render_template(
        "student/pay_credit_card.html",
        penalty=penalty,
        student_id=student_id
    )
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        card_number = request.form.get("card_number", "").strip()

        success, message = pay_penalty_with_credit_card(
            penalty_id,
            card_number
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_credit_card.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "student/pay_credit_card.html",
        penalty=penalty
    )


@penalty_bp.route("/student/pay-cash/<penalty_id>", methods=["GET", "POST"])
def student_pay_cash(penalty_id):
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
            or request.form.get("cash_amount")
            or penalty.get("penalty_amount")
        )

        success, message = pay_student_own_penalty(
            penalty_id,
            student_id,
            payment_amount,
            "Cash"
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_cash.html",
            penalty=penalty,
            student_id=student_id,
            error=message
        ), 400

    return render_template(
        "student/pay_cash.html",
        penalty=penalty,
        student_id=student_id
    )
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()

        success, message = pay_penalty_with_cash(
            penalty_id,
            cash_amount
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_cash.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "student/pay_cash.html",
        penalty=penalty
    )


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
        student_id=student_id
    )


@penalty_bp.route("/librarian/waive/<penalty_id>", methods=["GET", "POST"])
def librarian_waive_penalty(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        waiver_reason = request.form.get("waiver_reason", "").strip()
        waived_by = request.form.get("waived_by", "Librarian").strip()

        success, message = waive_penalty(
            penalty_id,
            waiver_reason,
            waived_by
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "librarian/waive_penalty.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "librarian/waive_penalty.html",
        penalty=penalty
    )

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
            transaction_id,
            rejection_reason,
            rejected_by
        )

        if not success:
            return render_template(
                "librarian/reject_return_exception.html",
                transaction=transaction,
                error=message
            ), 400

        penalty_success, penalty_message = create_penalty_record_for_rejected_return(
            transaction_id,
            penalty_amount,
            rejection_reason,
            rejected_by
        )

        if not penalty_success:
            return render_template(
                "librarian/reject_return_exception.html",
                transaction=transaction,
                error=penalty_message
            ), 400

        flash(message + " " + penalty_message, "success")
        return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

    return render_template(
        "librarian/reject_return_exception.html",
        transaction=transaction
    )

@penalty_bp.route("/librarian/book-exception/<transaction_id>", methods=["GET", "POST"])
def librarian_record_book_exception(transaction_id):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return "Transaction record not found", 404

    if request.method == "POST":
        exception_type = request.form.get("exception_type", "").strip()
        exception_description = request.form.get("exception_description", "").strip()
        recorded_by = request.form.get("recorded_by", "Librarian").strip()

        success, message = record_lost_damaged_book_exception(
            transaction_id,
            exception_type,
            exception_description,
            recorded_by
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.identify_overdue_books"))

        return render_template(
            "librarian/book_exception.html",
            transaction=transaction,
            error=message
        ), 400

    return render_template(
        "librarian/book_exception.html",
        transaction=transaction
    )

@penalty_bp.route("/librarian/check-borrow-approval/<request_id>", methods=["GET", "POST"])
def librarian_check_borrow_approval(request_id):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return "Borrow request not found", 404

    student_id = borrow_request.get("student_id")
    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if request.method == "POST":
        approved_by = request.form.get("approved_by", "Librarian").strip()

        success, message = approve_borrow_request_with_penalty_check(
            request_id,
            approved_by
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.librarian_check_borrow_approval", request_id=request_id))

        return render_template(
            "librarian/check_borrow_approval.html",
            borrow_request=borrow_request,
            unpaid_penalties=unpaid_penalties,
            error=message
        ), 400

    return render_template(
        "librarian/check_borrow_approval.html",
        borrow_request=borrow_request,
        unpaid_penalties=unpaid_penalties
    )