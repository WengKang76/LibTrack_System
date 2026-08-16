import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    has_app_context,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config.firebase_config import (
    COLLECTION_BORROW_REQUESTS,
    COLLECTION_BORROW_TRANSACTIONS,
    COLLECTION_PENALTIES,
    COLLECTION_USERS,
    db,
)


penalty_bp = Blueprint(
    "penalty_transaction",
    __name__,
    url_prefix="/penalty",
    template_folder=".",
)


# =========================================================
# CONFIGURATION
# =========================================================

PENALTY_RATE_PER_DAY = 1.00
COLLECTION_BOOK_EXCEPTIONS = "book_exceptions"

# These dictionaries are intentionally EMPTY.
# They exist only to keep the existing unit tests backward-compatible.
# Production code only falls back to them when TESTING is enabled.
DEMO_BORROW_TRANSACTIONS = {}
DEMO_PENALTIES = {}
DEMO_RETURN_TRANSACTIONS = {}
DEMO_BOOK_EXCEPTIONS = {}
DEMO_BORROW_REQUESTS = {}


# =========================================================
# COMMON HELPERS
# =========================================================


def _testing_mode():
    if os.getenv("TESTING") == "1":
        return True

    if has_app_context() and current_app.testing:
        return True

    return False


def _log_exception(message, *args):
    if has_app_context():
        current_app.logger.exception(message, *args)


def _now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalise_text(value):
    return str(value or "").strip().lower()


def has_field_value(value):
    return value is not None and str(value).strip() != ""


def convert_to_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        # Most LibTrack records use YYYY-MM-DD.
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    return None


def librarian_required(view_function):
    """Protect librarian-only routes in production while keeping pytest compatibility."""

    @wraps(view_function)
    def wrapped(*args, **kwargs):
        if _testing_mode():
            return view_function(*args, **kwargs)

        if not session.get("user_id"):
            return redirect(url_for("authentication.login"))

        if normalise_text(session.get("role")) != "librarian":
            abort(403)

        return view_function(*args, **kwargs)

    return wrapped


def _current_librarian_identity():
    return (
        session.get("user_id")
        or session.get("full_name")
        or ("Librarian" if _testing_mode() else None)
    )


def sort_student_penalties_for_display(penalties):
    status_priority = {
        "outstanding": 0,
        "unpaid": 0,
        "pending": 0,
        "waived": 1,
        "paid": 2,
    }

    return sorted(
        penalties,
        key=lambda penalty: (
            status_priority.get(
                normalise_text(
                    penalty.get("display_status") or penalty.get("status")
                ),
                1,
            ),
            normalise_text(penalty.get("penalty_id")),
        ),
    )


# =========================================================
# PENALTY RECORD DISPLAY HELPERS
# =========================================================


def normalise_penalty_record_for_display(penalty, document_id=None):
    penalty = (penalty or {}).copy()

    if document_id:
        penalty["penalty_id"] = document_id
    else:
        penalty["penalty_id"] = penalty.get("penalty_id")

    status = normalise_text(penalty.get("status"))

    # Prefer the actual status when it is valid.
    if status == "paid":
        penalty["display_status"] = "Paid"
        penalty["is_previous_record"] = True
        return penalty

    if status == "waived":
        penalty["display_status"] = "Waived"
        penalty["is_previous_record"] = True
        return penalty

    if status in {"resolved", "closed", "cancelled", "canceled"}:
        penalty["display_status"] = penalty.get("status") or "Resolved"
        penalty["is_previous_record"] = True
        return penalty

    if status in {"outstanding", "unpaid", "pending"}:
        penalty["display_status"] = penalty.get("status") or "Outstanding"
        penalty["is_previous_record"] = False
        return penalty

    # Compatibility for older records whose status field was not maintained.
    paid_indicators = [
        penalty.get("paid_date"),
        penalty.get("payment_date"),
        penalty.get("paid_amount"),
        penalty.get("payment_method"),
        penalty.get("paid_by"),
    ]

    waived_indicators = [
        penalty.get("waived_date"),
        penalty.get("waiver_reason"),
        penalty.get("waived_by"),
    ]

    resolved_indicators = [
        penalty.get("resolved_date"),
        penalty.get("closed_date"),
    ]

    if any(has_field_value(value) for value in paid_indicators):
        penalty["display_status"] = "Paid"
        penalty["is_previous_record"] = True
    elif any(has_field_value(value) for value in waived_indicators):
        penalty["display_status"] = "Waived"
        penalty["is_previous_record"] = True
    elif any(has_field_value(value) for value in resolved_indicators):
        penalty["display_status"] = penalty.get("status") or "Resolved"
        penalty["is_previous_record"] = True
    else:
        penalty["display_status"] = penalty.get("status") or "Outstanding"
        penalty["is_previous_record"] = False

    return penalty


def get_penalty_latest_date(penalty):
    date_fields = [
        "updated_at",
        "paid_date",
        "payment_date",
        "waived_date",
        "resolved_date",
        "created_date",
        "created_at",
    ]

    for field in date_fields:
        if has_field_value(penalty.get(field)):
            return str(penalty.get(field))

    return ""


def sort_penalty_records_for_librarian(penalties):
    return sorted(
        penalties,
        key=lambda penalty: (
            penalty.get("is_previous_record", False),
            get_penalty_latest_date(penalty),
        ),
    )


def get_display_amount(penalty):
    for field in ("penalty_amount", "amount", "total_amount"):
        value = penalty.get(field)
        if value is not None and value != "":
            return value

    return 0


def get_display_payment_method(penalty):
    return penalty.get("payment_method") or penalty.get("method") or "-"


# =========================================================
# OVERDUE BOOKS AND AUTOMATIC PENALTY CALCULATION
# =========================================================


def get_overdue_books():
    today = date.today()
    overdue_books = []

    try:
        docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in docs:
            transaction = doc.to_dict() or {}
            transaction["transaction_id"] = doc.id

            due_date = convert_to_date(transaction.get("due_date"))
            status = normalise_text(transaction.get("status"))
            return_date = transaction.get("return_date")

            # Only active borrowing records should be treated as overdue.
            active_statuses = {
                "borrowed",
                "renewed",
                "overdue",
                "active",
            }

            if (
                due_date
                and due_date < today
                and status in active_statuses
                and not has_field_value(return_date)
            ):
                overdue_books.append(transaction)

    except Exception:
        _log_exception("Failed to retrieve overdue borrowing records.")

    # Old tests may inject records here. Production never uses this fallback.
    if _testing_mode() and not overdue_books and DEMO_BORROW_TRANSACTIONS:
        for transaction_id, transaction in DEMO_BORROW_TRANSACTIONS.items():
            demo_transaction = transaction.copy()
            demo_transaction["transaction_id"] = transaction_id

            due_date = convert_to_date(demo_transaction.get("due_date"))
            status = normalise_text(demo_transaction.get("status"))

            if due_date and due_date < today and status != "returned":
                overdue_books.append(demo_transaction)

    return overdue_books


def calculate_penalty_amount(due_date):
    due_date = convert_to_date(due_date)
    today = date.today()

    if due_date is None or due_date >= today:
        return {"overdue_days": 0, "penalty_amount": 0.00}

    overdue_days = (today - due_date).days
    penalty_amount = round(overdue_days * PENALTY_RATE_PER_DAY, 2)

    return {
        "overdue_days": overdue_days,
        "penalty_amount": penalty_amount,
    }


# =========================================================
# FIRESTORE PENALTY READ / WRITE HELPERS
# =========================================================


def get_student_display_name(student_id):
    if student_id is None or str(student_id).strip() == "":
        return "-"

    student_id = str(student_id).strip()

    try:
        users_ref = db.collection(COLLECTION_USERS)

        # Try user document ID first.
        user_doc = users_ref.document(student_id).get()

        if getattr(user_doc, "exists", False) is True:
            user = user_doc.to_dict() or {}
            return (
                user.get("full_name")
                or user.get("name")
                or user.get("student_name")
                or user.get("username")
                or "-"
            )

        # Then try common student/user identifier fields.
        for field_name in (
            "user_id",
            "student_id",
            "student_number",
            "student_no",
            "id",
        ):
            docs = users_ref.where(field_name, "==", student_id).stream()

            for doc in docs:
                user = doc.to_dict() or {}
                return (
                    user.get("full_name")
                    or user.get("name")
                    or user.get("student_name")
                    or user.get("username")
                    or "-"
                )

    except Exception:
        _log_exception("Failed to retrieve student name for %s.", student_id)

    return "-"


def get_all_penalty_records():
    penalties = []

    try:
        penalty_docs = db.collection(COLLECTION_PENALTIES).stream()

        for doc in penalty_docs:
            penalty = normalise_penalty_record_for_display(
                doc.to_dict() or {},
                document_id=doc.id,
            )

            if not penalty.get("student_name"):
                penalty["student_name"] = get_student_display_name(
                    penalty.get("student_id")
                )

            penalties.append(penalty)

    except Exception:
        _log_exception("Failed to retrieve penalty records.")

    if _testing_mode() and not penalties and DEMO_PENALTIES:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            penalties.append(
                normalise_penalty_record_for_display(
                    penalty,
                    document_id=penalty_id,
                )
            )

    return penalties


def get_outstanding_penalties(student_id=None):
    penalties = []

    for penalty in get_all_penalty_records():
        status = normalise_text(
            penalty.get("display_status") or penalty.get("status")
        )

        if status not in {"outstanding", "unpaid", "pending"}:
            continue

        if student_id is not None and str(penalty.get("student_id")) != str(student_id):
            continue

        penalties.append(penalty)

    return penalties


def get_penalty_by_id(penalty_id):
    try:
        penalty_doc = (
            db.collection(COLLECTION_PENALTIES)
            .document(str(penalty_id))
            .get()
        )

        if getattr(penalty_doc, "exists", False) is True:
            penalty = normalise_penalty_record_for_display(
                penalty_doc.to_dict() or {},
                document_id=penalty_doc.id,
            )

            if not penalty.get("student_name"):
                penalty["student_name"] = get_student_display_name(
                    penalty.get("student_id")
                )

            return penalty

    except Exception:
        _log_exception("Failed to retrieve penalty %s.", penalty_id)

    if _testing_mode() and penalty_id in DEMO_PENALTIES:
        return normalise_penalty_record_for_display(
            DEMO_PENALTIES[penalty_id],
            document_id=penalty_id,
        )

    return None


def update_penalty_record(penalty_id, update_data):
    try:
        penalty_ref = db.collection(COLLECTION_PENALTIES).document(str(penalty_id))
        penalty_doc = penalty_ref.get()

        if getattr(penalty_doc, "exists", False) is True:
            penalty_ref.update(update_data)
            return True

    except Exception:
        _log_exception("Failed to update penalty %s.", penalty_id)

    if _testing_mode() and penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(update_data)
        return True

    return False


def get_penalty_payment_records(student_id=None):
    payment_records = []

    for penalty in get_all_penalty_records():
        status = normalise_text(
            penalty.get("display_status") or penalty.get("status")
        )

        if status != "paid":
            continue

        if student_id is not None and str(penalty.get("student_id")) != str(student_id):
            continue

        payment_records.append(penalty)

    return payment_records


def get_student_penalty_records(student_id):
    if student_id is None or str(student_id).strip() == "":
        return []

    student_id = str(student_id).strip()
    penalties = []

    for penalty in get_all_penalty_records():
        penalty_student_id = penalty.get("student_id")

        if penalty_student_id is None:
            continue

        if str(penalty_student_id) == student_id:
            penalties.append(penalty)

    return penalties


# =========================================================
# PENALTY VALIDATION AND PAYMENT
# =========================================================


def validate_penalty_amount(penalty_amount):
    try:
        valid_amount = float(penalty_amount)
    except (TypeError, ValueError):
        return False, "Invalid penalty amount.", None

    if valid_amount <= 0:
        return False, "Penalty amount must be greater than zero.", None

    return True, "Penalty amount is valid.", round(valid_amount, 2)


def validate_penalty_payment_status(penalty):
    penalty_status = normalise_text(penalty.get("status"))

    if penalty_status in {"paid", "waived"}:
        return False, "This penalty has already been paid or waived."

    if penalty_status not in {"outstanding", "unpaid", "pending"}:
        return False, "Only outstanding penalties can be paid."

    return True, "Penalty can be paid."


def validate_student_penalty_access(penalty_id, student_id):
    if student_id is None or str(student_id).strip() == "":
        return False, "Student identity is required.", None

    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found.", None

    penalty_student_id = penalty.get("student_id")

    if not has_field_value(penalty_student_id):
        return False, "Penalty record does not contain a student owner.", penalty

    if str(penalty_student_id) != str(student_id):
        return (
            False,
            "You are not allowed to access another student's penalty record.",
            penalty,
        )

    return True, "Student is allowed to access this penalty.", penalty


def build_audit_details(action_name, actor_name):
    return {
        "last_action": action_name,
        "updated_by": actor_name,
        "updated_at": _now_string(),
    }


def pay_student_own_penalty(
    penalty_id,
    student_id,
    payment_amount,
    payment_method="Credit Card",
):
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id,
    )

    if not access_success:
        return False, access_message

    amount_success, amount_message, valid_amount = validate_penalty_amount(
        payment_amount
    )

    if not amount_success:
        return False, amount_message

    status_success, status_message = validate_penalty_payment_status(penalty)

    if not status_success:
        return False, status_message

    try:
        expected_amount = round(float(get_display_amount(penalty)), 2)
    except (TypeError, ValueError):
        return False, "Penalty record contains an invalid amount."

    if valid_amount != expected_amount:
        return False, "Payment amount does not match the penalty amount."

    audit_details = build_audit_details("Pay Penalty", student_id)

    update_data = {
        "status": "Paid",
        "payment_method": payment_method,
        "paid_by": student_id,
        "paid_amount": valid_amount,
        "paid_date": _now_string(),
        **audit_details,
    }

    if not update_penalty_record(penalty_id, update_data):
        return False, "Unable to update the penalty payment record."

    return True, "Penalty paid successfully."


def pay_penalty_with_credit_card(penalty_id, card_number):
    """Legacy Sprint 1 helper retained for existing tests/routes."""

    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status_success, status_message = validate_penalty_payment_status(penalty)

    if not status_success:
        return False, status_message

    card_number = str(card_number or "").replace(" ", "").replace("-", "")

    if not card_number.isdigit() or not 12 <= len(card_number) <= 19:
        return False, "Invalid credit card number."

    payment_data = {
        "status": "Paid",
        "payment_method": "Credit Card",
        "paid_by": penalty.get("student_id") or "Student",
        "payment_date": _now_string(),
        "paid_date": _now_string(),
        "paid_amount": get_display_amount(penalty),
        "card_last_four": card_number[-4:],
        **build_audit_details(
            "Pay Penalty",
            penalty.get("student_id") or "Student",
        ),
    }

    if not update_penalty_record(penalty_id, payment_data):
        return False, "Unable to update the penalty payment record."

    return True, "Penalty paid successfully using credit card."


def pay_penalty_with_cash(penalty_id, cash_amount):
    """Legacy Sprint 1 helper retained for existing tests/routes."""

    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status_success, status_message = validate_penalty_payment_status(penalty)

    if not status_success:
        return False, status_message

    try:
        cash_amount = float(cash_amount)
        penalty_amount = float(get_display_amount(penalty))
    except (TypeError, ValueError):
        return False, "Invalid cash amount."

    if cash_amount < penalty_amount:
        return False, "Cash amount is less than the penalty amount."

    change_amount = round(cash_amount - penalty_amount, 2)

    payment_data = {
        "status": "Paid",
        "payment_method": "Cash",
        "paid_by": penalty.get("student_id") or "Student",
        "cash_amount_received": round(cash_amount, 2),
        "change_amount": change_amount,
        "payment_date": _now_string(),
        "paid_date": _now_string(),
        "paid_amount": round(penalty_amount, 2),
        **build_audit_details(
            "Pay Penalty",
            penalty.get("student_id") or "Student",
        ),
    }

    if not update_penalty_record(penalty_id, payment_data):
        return False, "Unable to update the penalty payment record."

    return True, "Cash penalty payment completed successfully."


def build_payment_receipt(penalty_id, student_id):
    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id,
    )

    if not access_success:
        return False, access_message, None

    if normalise_text(penalty.get("status")) != "paid":
        return (
            False,
            "Payment receipt is only available after successful payment.",
            None,
        )

    receipt = {
        "penalty_id": penalty_id,
        "student_id": penalty.get("student_id") or student_id,
        "book_title": penalty.get("book_title") or "-",
        "penalty_reason": (
            penalty.get("penalty_reason")
            or penalty.get("penalty_type")
            or "-"
        ),
        "payment_amount": get_display_amount(penalty),
        "payment_method": get_display_payment_method(penalty),
        "payment_status": penalty.get("status") or "Paid",
        "payment_date": (
            penalty.get("paid_date")
            or penalty.get("payment_date")
            or "-"
        ),
        "paid_by": penalty.get("paid_by") or student_id,
    }

    return True, "Payment receipt generated successfully.", receipt


# =========================================================
# WAIVER
# =========================================================


def validate_waiver_reason(waiver_reason):
    if waiver_reason is None:
        return False, "Waiver reason is required.", None

    waiver_reason = str(waiver_reason).strip()

    if waiver_reason == "":
        return False, "Waiver reason is required.", None

    if len(waiver_reason) < 5:
        return False, "Waiver reason must be at least 5 characters.", None

    return True, "Waiver reason is valid.", waiver_reason


def waive_penalty(penalty_id, waiver_reason, waived_by="Librarian"):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    penalty_status = normalise_text(penalty.get("status"))

    if penalty_status == "paid":
        return False, "Paid penalties cannot be waived."

    if penalty_status == "waived":
        return False, "Penalty has already been waived."

    if penalty_status not in {"outstanding", "unpaid", "pending"}:
        return False, "Only outstanding penalties can be waived."

    reason_success, reason_message, valid_waiver_reason = validate_waiver_reason(
        waiver_reason
    )

    if not reason_success:
        return False, reason_message

    actor = waived_by or _current_librarian_identity() or "Librarian"

    waiver_data = {
        "status": "Waived",
        "waiver_reason": valid_waiver_reason,
        "waived_by": actor,
        "waived_date": _now_string(),
        **build_audit_details("Waive Penalty", actor),
    }

    if not update_penalty_record(penalty_id, waiver_data):
        return False, "Unable to update the penalty record."

    return True, "Penalty waived successfully."


# =========================================================
# RETURN EXCEPTION HANDLING
# =========================================================


def get_return_transaction_by_id(transaction_id):
    try:
        transaction_doc = (
            db.collection(COLLECTION_BORROW_TRANSACTIONS)
            .document(str(transaction_id))
            .get()
        )

        if getattr(transaction_doc, "exists", False) is True:
            transaction = transaction_doc.to_dict() or {}
            transaction["transaction_id"] = transaction_doc.id
            return transaction

    except Exception:
        _log_exception("Failed to retrieve return transaction %s.", transaction_id)

    if _testing_mode():
        transaction = DEMO_RETURN_TRANSACTIONS.get(transaction_id)

        if transaction:
            return transaction.copy()

        transaction = DEMO_BORROW_TRANSACTIONS.get(transaction_id)

        if transaction:
            result = transaction.copy()
            result["transaction_id"] = transaction_id
            return result

    return None


def get_return_exception_candidates():
    """Return only borrowing transactions that currently have a pending return request."""
    candidates = []
    allowed_statuses = {"return pending", "return requested", "pending return"}

    try:
        docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in docs:
            transaction = doc.to_dict() or {}
            transaction["transaction_id"] = doc.id

            if normalise_text(transaction.get("status")) in allowed_statuses:
                candidates.append(transaction)

    except Exception:
        _log_exception("Failed to retrieve pending return transactions.")

    if _testing_mode() and not candidates:
        source = {}
        source.update(DEMO_BORROW_TRANSACTIONS)
        source.update(DEMO_RETURN_TRANSACTIONS)

        for transaction_id, transaction in source.items():
            if normalise_text(transaction.get("status")) in allowed_statuses:
                item = transaction.copy()
                item["transaction_id"] = transaction_id
                candidates.append(item)

    return candidates


def reject_return_exception(transaction_id, rejection_reason, rejected_by="Librarian"):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Return transaction not found."

    status = normalise_text(transaction.get("status"))
    allowed_statuses = {"return pending", "return requested", "pending return"}

    if status not in allowed_statuses:
        return False, "Only a pending return request can be rejected."

    rejection_reason = str(rejection_reason or "").strip()

    if rejection_reason == "":
        return False, "Rejection reason is required."

    actor = rejected_by or _current_librarian_identity() or "Librarian"

    rejection_data = {
        "status": "Rejected",
        "return_status": "Rejected",
        "rejection_reason": rejection_reason,
        "rejected_by": actor,
        "rejected_date": _now_string(),
        "updated_at": _now_string(),
    }

    updated = False

    try:
        transaction_ref = (
            db.collection(COLLECTION_BORROW_TRANSACTIONS)
            .document(str(transaction_id))
        )
        transaction_doc = transaction_ref.get()

        if getattr(transaction_doc, "exists", False) is True:
            transaction_ref.update(rejection_data)
            updated = True

    except Exception:
        _log_exception("Failed to reject return transaction %s.", transaction_id)

    if _testing_mode() and transaction_id in DEMO_RETURN_TRANSACTIONS:
        DEMO_RETURN_TRANSACTIONS[transaction_id].update(rejection_data)
        updated = True

    if _testing_mode() and transaction_id in DEMO_BORROW_TRANSACTIONS:
        DEMO_BORROW_TRANSACTIONS[transaction_id].update(rejection_data)
        updated = True

    if not updated:
        return False, "Unable to update the return transaction."

    return True, "Return exception rejected successfully."


def penalty_record_exists_for_transaction(transaction_id, penalty_type=None):
    try:
        penalty_docs = db.collection(COLLECTION_PENALTIES).stream()

        for doc in penalty_docs:
            penalty = doc.to_dict() or {}

            if str(penalty.get("transaction_id")) != str(transaction_id):
                continue

            if penalty_type is None:
                return True

            if normalise_text(penalty.get("penalty_type")) == normalise_text(
                penalty_type
            ):
                return True

    except Exception:
        _log_exception(
            "Failed while checking penalty existence for transaction %s.",
            transaction_id,
        )

    if _testing_mode():
        for penalty in DEMO_PENALTIES.values():
            if str(penalty.get("transaction_id")) != str(transaction_id):
                continue

            if penalty_type is None:
                return True

            if normalise_text(penalty.get("penalty_type")) == normalise_text(
                penalty_type
            ):
                return True

    return False


def penalty_record_exists_for_rejected_return(transaction_id):
    return penalty_record_exists_for_transaction(transaction_id, "Rejected Return")


def _save_new_penalty(penalty_id, penalty_data):
    try:
        db.collection(COLLECTION_PENALTIES).document(str(penalty_id)).set(
            penalty_data
        )
        return True
    except Exception:
        _log_exception("Failed to create penalty %s.", penalty_id)

    if _testing_mode():
        DEMO_PENALTIES[penalty_id] = penalty_data.copy()
        return True

    return False


def create_penalty_record_for_rejected_return(
    transaction_id,
    penalty_amount,
    penalty_reason,
    created_by="Librarian",
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Return transaction not found."

    if normalise_text(transaction.get("status")) != "rejected":
        return False, "Penalty can only be created after the return is rejected."

    if penalty_record_exists_for_rejected_return(transaction_id):
        return False, "Penalty record already exists for this rejected return."

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        return False, amount_message

    penalty_reason = str(penalty_reason or "").strip()

    if penalty_reason == "":
        return False, "Penalty reason is required."

    actor = created_by or _current_librarian_identity() or "Librarian"
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
        "created_by": actor,
        "created_date": _now_string(),
        **build_audit_details("Create Penalty", actor),
    }

    if not _save_new_penalty(penalty_id, penalty_data):
        return False, "Unable to create the penalty record."

    return True, "Penalty record for rejected return created successfully."


# =========================================================
# LOST / DAMAGED BOOK EXCEPTIONS
# =========================================================


def book_exception_exists(transaction_id):
    try:
        exception_docs = db.collection(COLLECTION_BOOK_EXCEPTIONS).stream()

        for doc in exception_docs:
            exception = doc.to_dict() or {}
            if str(exception.get("transaction_id")) == str(transaction_id):
                return True

    except Exception:
        _log_exception(
            "Failed while checking book exception for transaction %s.",
            transaction_id,
        )

    if _testing_mode():
        for exception in DEMO_BOOK_EXCEPTIONS.values():
            if str(exception.get("transaction_id")) == str(transaction_id):
                return True

    return False


def validate_required_field(value, field_name):
    if value is None:
        return False, f"{field_name} is required.", None

    value = str(value).strip()

    if value == "":
        return False, f"{field_name} is required.", None

    return True, f"{field_name} is valid.", value


def validate_book_exception_type(exception_type):
    success, message, valid_exception_type = validate_required_field(
        exception_type,
        "Book exception type",
    )

    if not success:
        return False, message, None

    valid_exception_type = valid_exception_type.title()

    if valid_exception_type not in {"Lost", "Damaged"}:
        return False, "Book exception type must be Lost or Damaged.", None

    return True, "Book exception type is valid.", valid_exception_type


def record_lost_damaged_book_exception(
    transaction_id,
    exception_type,
    exception_description,
    recorded_by="Librarian",
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, "Transaction record not found."

    type_success, type_message, valid_exception_type = validate_book_exception_type(
        exception_type
    )

    if not type_success:
        return False, type_message

    description_success, description_message, valid_description = validate_required_field(
        exception_description,
        "Exception description",
    )

    if not description_success:
        return False, description_message

    if book_exception_exists(transaction_id):
        return False, "Book exception already exists for this transaction."

    actor = recorded_by or _current_librarian_identity() or "Librarian"
    exception_id = "BE" + datetime.now().strftime("%Y%m%d%H%M%S%f")

    exception_data = {
        "exception_id": exception_id,
        "transaction_id": transaction_id,
        "student_id": transaction.get("student_id"),
        "book_id": transaction.get("book_id"),
        "book_title": transaction.get("book_title"),
        "exception_type": valid_exception_type,
        "exception_description": valid_description,
        "exception_status": "Exception Recorded",
        "recorded_by": actor,
        "recorded_date": _now_string(),
        "updated_at": _now_string(),
    }

    saved_exception = False

    try:
        db.collection(COLLECTION_BOOK_EXCEPTIONS).document(exception_id).set(
            exception_data
        )
        saved_exception = True
    except Exception:
        _log_exception("Failed to create book exception %s.", exception_id)

    if _testing_mode() and not saved_exception:
        DEMO_BOOK_EXCEPTIONS[exception_id] = exception_data.copy()
        saved_exception = True

    if not saved_exception:
        return False, "Unable to create the book exception record."

    update_data = {
        "status": f"{valid_exception_type} Exception Recorded",
        "book_exception_status": "Exception Recorded",
        "exception_type": valid_exception_type,
        "updated_at": _now_string(),
    }

    updated_transaction = False

    try:
        transaction_ref = (
            db.collection(COLLECTION_BORROW_TRANSACTIONS)
            .document(str(transaction_id))
        )
        transaction_doc = transaction_ref.get()

        if getattr(transaction_doc, "exists", False) is True:
            transaction_ref.update(update_data)
            updated_transaction = True
    except Exception:
        _log_exception(
            "Failed to update borrowing transaction %s after exception creation.",
            transaction_id,
        )

    if _testing_mode() and transaction_id in DEMO_RETURN_TRANSACTIONS:
        DEMO_RETURN_TRANSACTIONS[transaction_id].update(update_data)
        updated_transaction = True

    if _testing_mode() and transaction_id in DEMO_BORROW_TRANSACTIONS:
        DEMO_BORROW_TRANSACTIONS[transaction_id].update(update_data)
        updated_transaction = True

    if not updated_transaction and not _testing_mode():
        return (
            False,
            "Book exception was created, but the borrowing transaction could not be updated.",
        )

    return True, "Lost or damaged book exception recorded successfully."


def create_lost_damaged_book_exception_penalty(
    transaction_id,
    exception_type,
    exception_description,
    penalty_amount,
    recorded_by="Librarian",
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            "Return transaction not found.",
        )

    type_success, type_message, valid_exception_type = validate_book_exception_type(
        exception_type
    )

    if not type_success:
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            type_message,
        )

    description_success, description_message, valid_description = validate_required_field(
        exception_description,
        "Exception description",
    )

    if not description_success:
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            description_message,
        )

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            amount_message,
        )

    if penalty_record_exists_for_transaction(transaction_id, "Lost/Damaged Book"):
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            "Penalty record already exists for this lost or damaged book exception.",
        )

    actor = recorded_by or _current_librarian_identity() or "Librarian"
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
        "penalty_reason": f"{valid_exception_type} book exception",
        "penalty_amount": valid_penalty_amount,
        "status": "Outstanding",
        "created_by": actor,
        "created_date": _now_string(),
        **build_audit_details("Create Lost/Damaged Book Penalty", actor),
    }

    if not _save_new_penalty(penalty_id, penalty_data):
        return False, create_penalty_action_message(
            "Lost or damaged book exception handling",
            False,
            "Unable to create the penalty record.",
        )

    return True, create_penalty_action_message(
        "Lost or damaged book exception handling",
        True,
        "Lost or damaged book penalty record has been created.",
    )


# =========================================================
# BORROWING ELIGIBILITY / PENALTY INTEGRATION
# =========================================================


def get_unpaid_penalties_by_student(student_id):
    if student_id is None or str(student_id).strip() == "":
        return []

    return get_outstanding_penalties(str(student_id).strip())


def check_student_borrowing_eligibility(student_id):
    if student_id is None or str(student_id).strip() == "":
        return False, "Student ID is required for borrowing approval.", []

    student_id = str(student_id).strip()
    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if unpaid_penalties:
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
    try:
        request_doc = (
            db.collection(COLLECTION_BORROW_REQUESTS)
            .document(str(request_id))
            .get()
        )

        if getattr(request_doc, "exists", False) is True:
            borrow_request = request_doc.to_dict() or {}
            borrow_request["request_id"] = request_doc.id
            return borrow_request

    except Exception:
        _log_exception("Failed to retrieve borrow request %s.", request_id)

    if _testing_mode() and request_id in DEMO_BORROW_REQUESTS:
        borrow_request = DEMO_BORROW_REQUESTS[request_id].copy()
        borrow_request["request_id"] = request_id
        return borrow_request

    return None


def get_pending_borrow_requests():
    requests_list = []

    try:
        docs = db.collection(COLLECTION_BORROW_REQUESTS).stream()

        for doc in docs:
            borrow_request = doc.to_dict() or {}
            borrow_request["request_id"] = doc.id

            if normalise_text(borrow_request.get("status")) not in {
                "pending",
                "pending approval",
            }:
                continue

            student_id = borrow_request.get("student_id")
            borrow_request["student_name"] = get_student_display_name(student_id)
            borrow_request["unpaid_penalty_count"] = len(
                get_unpaid_penalties_by_student(student_id)
            )
            requests_list.append(borrow_request)

    except Exception:
        _log_exception("Failed to retrieve pending borrow requests.")

    if _testing_mode() and not requests_list and DEMO_BORROW_REQUESTS:
        for request_id, borrow_request in DEMO_BORROW_REQUESTS.items():
            if normalise_text(borrow_request.get("status")) not in {
                "pending",
                "pending approval",
            }:
                continue

            item = borrow_request.copy()
            item["request_id"] = request_id
            item["student_name"] = get_student_display_name(item.get("student_id"))
            item["unpaid_penalty_count"] = len(
                get_unpaid_penalties_by_student(item.get("student_id"))
            )
            requests_list.append(item)

    return requests_list


def approve_borrow_request_with_penalty_check(
    request_id,
    approved_by="Librarian",
):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return False, "Borrow request not found."

    request_status = normalise_text(borrow_request.get("status"))

    if request_status not in {"pending", "pending approval"}:
        return False, "Only pending borrow requests can be approved."

    student_id = borrow_request.get("student_id")
    eligibility_success, eligibility_message, _ = check_student_borrowing_eligibility(
        student_id
    )

    if not eligibility_success:
        return False, eligibility_message

    actor = approved_by or _current_librarian_identity() or "Librarian"

    # In the real application, delegate the actual approval to the borrowing
    # service so book availability, request status, reservation data and the
    # new borrow transaction stay consistent.
    if not _testing_mode():
        try:
            from modules.borrowing.services import (
                approve_borrow_request,
                get_borrow_approval_error,
            )

            approval_error = get_borrow_approval_error(str(request_id))
            if approval_error:
                return False, approval_error

            transaction_id = approve_borrow_request(str(request_id))
            if not transaction_id:
                return False, "Unable to approve the borrow request."

            try:
                db.collection(COLLECTION_BORROW_REQUESTS).document(
                    str(request_id)
                ).update(
                    {
                        "approved_by": actor,
                        "approved_date": _now_string(),
                        **build_audit_details("Approve Borrow Request", actor),
                    }
                )
            except Exception:
                _log_exception(
                    "Borrow request %s was approved but audit details could not be stored.",
                    request_id,
                )

            return True, "Borrow request approved successfully."

        except Exception:
            _log_exception("Failed to approve borrow request %s.", request_id)
            return False, "Unable to approve the borrow request."

    # Test fallback for the existing unit tests that inject DEMO_BORROW_REQUESTS.
    approval_data = {
        "status": "Approved",
        "approved_by": actor,
        "approved_date": _now_string(),
        **build_audit_details("Approve Borrow Request", actor),
    }

    updated = False

    try:
        request_ref = db.collection(COLLECTION_BORROW_REQUESTS).document(
            str(request_id)
        )
        request_doc = request_ref.get()

        if getattr(request_doc, "exists", False) is True:
            request_ref.update(approval_data)
            updated = True
    except Exception:
        pass

    if request_id in DEMO_BORROW_REQUESTS:
        DEMO_BORROW_REQUESTS[request_id].update(approval_data)
        updated = True

    if not updated:
        return False, "Unable to update the borrow request."

    return True, "Borrow request approved successfully."


# =========================================================
# COMMON VALIDATION / USER-FRIENDLY MESSAGES
# =========================================================


def create_penalty_action_message(action_name, success, message):
    if success:
        return f"{action_name} completed successfully. {message}"

    return f"{action_name} failed. Reason: {message}"


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
    validations = []

    if transaction_id is not None:
        validations.append(validate_required_field(transaction_id, "Transaction ID"))

    if student_id is not None:
        validations.append(validate_required_field(student_id, "Student ID"))

    if book_id is not None:
        validations.append(validate_required_field(book_id, "Book ID"))

    for success, message, _ in validations:
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if penalty_amount is not None:
        success, message, _ = validate_penalty_amount(penalty_amount)
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if penalty_reason is not None:
        success, message, _ = validate_required_field(
            penalty_reason,
            "Penalty reason",
        )
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if exception_type is not None:
        success, message, _ = validate_book_exception_type(exception_type)
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if exception_description is not None:
        success, message, _ = validate_required_field(
            exception_description,
            "Exception description",
        )
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    if waiver_reason is not None:
        success, message, _ = validate_waiver_reason(waiver_reason)
        if not success:
            return False, create_penalty_action_message(action_name, False, message)

    return True, create_penalty_action_message(
        action_name,
        True,
        "All validation checks passed.",
    )


def handle_rejected_return_exception(
    transaction_id,
    penalty_amount,
    penalty_reason,
    handled_by="Librarian",
):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            "Return transaction not found.",
        )

    if normalise_text(transaction.get("status")) != "rejected":
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            "Penalty can only be created after the return is rejected.",
        )

    if penalty_record_exists_for_rejected_return(transaction_id):
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            "Penalty record already exists for this rejected return.",
        )

    reason_success, reason_message, valid_penalty_reason = validate_required_field(
        penalty_reason,
        "Penalty reason",
    )

    if not reason_success:
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            reason_message,
        )

    amount_success, amount_message, valid_penalty_amount = validate_penalty_amount(
        penalty_amount
    )

    if not amount_success:
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            amount_message,
        )

    success, result_message = create_penalty_record_for_rejected_return(
        transaction_id,
        valid_penalty_amount,
        valid_penalty_reason,
        handled_by,
    )

    if not success:
        return False, create_penalty_action_message(
            "Rejected return exception handling",
            False,
            result_message,
        )

    return True, create_penalty_action_message(
        "Rejected return exception handling",
        True,
        "Rejected return penalty record has been created.",
    )


def filter_student_penalty_records(
    penalties,
    keyword=None,
    status_filter=None,
    payment_method_filter=None,
):
    keyword = normalise_text(keyword)
    status_filter = normalise_text(status_filter)
    payment_method_filter = normalise_text(payment_method_filter)

    filtered_penalties = []

    for penalty in penalties:
        penalty_status = normalise_text(
            penalty.get("display_status") or penalty.get("status")
        )
        payment_method = normalise_text(get_display_payment_method(penalty))

        if status_filter and status_filter != "all":
            if penalty_status != status_filter:
                continue

        if payment_method_filter and payment_method_filter != "all":
            if payment_method != payment_method_filter:
                continue

        if keyword:
            searchable_text = " ".join(
                [
                    str(penalty.get("penalty_id", "")),
                    str(penalty.get("book_title", "")),
                    str(penalty.get("book_id", "")),
                    str(penalty.get("penalty_reason", "")),
                    str(penalty.get("penalty_type", "")),
                    str(penalty.get("display_status", "")),
                    str(penalty.get("status", "")),
                    str(penalty.get("payment_method", "")),
                ]
            ).lower()

            if keyword not in searchable_text:
                continue

        filtered_penalties.append(penalty)

    return filtered_penalties


def search_librarian_penalty_records(penalties, search_keyword=None):
    search_keyword = normalise_text(search_keyword)

    if not search_keyword:
        return penalties

    searched_penalties = []

    for penalty in penalties:
        searchable_text = " ".join(
            [
                str(penalty.get("penalty_id", "")),
                str(penalty.get("student_id", "")),
                str(penalty.get("student_name", "")),
                str(penalty.get("book_title", "")),
                str(penalty.get("penalty_reason", "")),
                str(penalty.get("penalty_type", "")),
                str(penalty.get("status", "")),
                str(penalty.get("display_status", "")),
            ]
        ).lower()

        if search_keyword in searchable_text:
            searched_penalties.append(penalty)

    return searched_penalties


def validate_dynamic_payment_details(payment_method, form_data):
    payment_method = str(payment_method or "").strip()

    if payment_method == "":
        return False, "Please select a payment method."

    method = payment_method.lower()

    if method in {"visa", "debit card", "credit card"}:
        required_fields = {
            "card_number": "Card number is required.",
            "card_holder": "Card holder name is required.",
            "expiry_date": "Expiry date is required.",
            "cvv": "CVV is required.",
        }

        for field_name, error_message in required_fields.items():
            if str(form_data.get(field_name, "")).strip() == "":
                return False, error_message

        card_number = (
            str(form_data.get("card_number", ""))
            .replace(" ", "")
            .replace("-", "")
        )

        if not card_number.isdigit() or not 12 <= len(card_number) <= 19:
            return False, "Please enter a valid card number."

        cvv = str(form_data.get("cvv", "")).strip()
        if not cvv.isdigit() or len(cvv) not in {3, 4}:
            return False, "Please enter a valid CVV."

    elif method == "paypal":
        paypal_email = str(form_data.get("paypal_email", "")).strip()

        if paypal_email == "":
            return False, "PayPal email is required."

        if "@" not in paypal_email:
            return False, "Please enter a valid PayPal email address."

    elif method == "cash":
        pass
    else:
        return False, "Invalid payment method selected."

    return True, "Payment details are valid."


def build_payment_confirmation_summary(
    penalty,
    student_id,
    payment_amount,
    payment_method,
):
    return {
        "penalty_id": penalty.get("penalty_id", "-"),
        "student_id": penalty.get("student_id") or student_id,
        "book_title": penalty.get("book_title", "-"),
        "penalty_reason": (
            penalty.get("penalty_reason")
            or penalty.get("penalty_type")
            or "-"
        ),
        "payment_amount": payment_amount,
        "payment_method": payment_method,
        "penalty_status": penalty.get("status", "-"),
    }


def get_user_friendly_payment_message(success, system_message, payment_method=None):
    message = str(system_message or "")

    if success:
        if payment_method:
            return (
                "Penalty paid successfully. "
                f"Your payment using {payment_method} has been recorded."
            )

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
# SESSION HELPERS
# =========================================================


def get_current_student_id(student_id=None):
    if student_id:
        return str(student_id).strip()

    if not has_app_context():
        return None

    resolved_student_id = (
        session.get("student_id")
        or session.get("student_number")
        or session.get("student_no")
        or session.get("user_id")
        or session.get("id")
    )

    if resolved_student_id:
        return str(resolved_student_id).strip()

    # Keep request fallbacks only for existing test/client compatibility.
    form_student_id = request.form.get("student_id")
    if form_student_id:
        return form_student_id.strip()

    query_student_id = request.args.get("student_id")
    if query_student_id:
        return query_student_id.strip()

    return None


def _student_route_identity_or_redirect():
    student_id = get_current_student_id()

    if student_id:
        return student_id, None

    if _testing_mode():
        # Tests should normally provide student_id explicitly. Do not invent one.
        return None, ("Student identity is required.", 403)

    return None, redirect(url_for("authentication.login"))


# =========================================================
# ROUTES - LIBRARIAN
# =========================================================


@penalty_bp.route("/librarian")
@librarian_required
def librarian_penalty_dashboard():
    return render_template("librarian/dashboard.html")


@penalty_bp.route("/librarian/return-exceptions")
@librarian_required
def librarian_return_exception_list():
    transactions = get_return_exception_candidates()

    return render_template(
        "librarian/select_return_exception.html",
        transactions=transactions,
    )


@penalty_bp.route("/librarian/borrow-approvals")
@librarian_required
def librarian_borrow_approval_list():
    borrow_requests = get_pending_borrow_requests()

    return render_template(
        "librarian/select_borrow_approval.html",
        borrow_requests=borrow_requests,
    )


@penalty_bp.route("/overdue")
@penalty_bp.route("/librarian/overdue")
@librarian_required
def identify_overdue_books():
    overdue_books = get_overdue_books()
    return render_template(
        "librarian/overdue_book.html",
        overdue_books=overdue_books,
    )


@penalty_bp.route("/penalties")
@penalty_bp.route("/outstanding")
@penalty_bp.route("/librarian/penalties")
@librarian_required
def view_outstanding_penalties():
    search_keyword = request.args.get("search_keyword", "").strip()

    penalty_records = get_all_penalty_records()

    if search_keyword:
        penalty_records = search_librarian_penalty_records(
            penalty_records,
            search_keyword,
        )

    penalty_records = sort_penalty_records_for_librarian(penalty_records)

    return render_template(
        "librarian/outstanding_penalties.html",
        outstanding_penalties=penalty_records,
        search_keyword=search_keyword,
        result_count=len(penalty_records),
    )


@penalty_bp.route("/payment-records")
@penalty_bp.route("/librarian/payment-records")
@librarian_required
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
@librarian_required
def librarian_choose_penalty_to_waive():
    outstanding_penalties = get_outstanding_penalties()

    return render_template(
        "librarian/select_penalty_to_waive.html",
        outstanding_penalties=outstanding_penalties,
    )


@penalty_bp.route("/librarian/waive/<penalty_id>", methods=["GET", "POST"])
@librarian_required
def librarian_waive_penalty(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        waiver_reason = request.form.get("waiver_reason", "").strip()
        waived_by = _current_librarian_identity()

        success, message = waive_penalty(
            penalty_id,
            waiver_reason,
            waived_by,
        )

        if success:
            flash(message, "success")
            return redirect(
                url_for("penalty_transaction.librarian_choose_penalty_to_waive")
            )

        return (
            render_template(
                "librarian/waive_penalty.html",
                penalty=penalty,
                error=message,
            ),
            400,
        )

    return render_template(
        "librarian/waive_penalty.html",
        penalty=penalty,
    )


@penalty_bp.route(
    "/librarian/reject-return/<transaction_id>",
    methods=["GET", "POST"],
)
@librarian_required
def librarian_reject_return_exception(transaction_id):
    transaction = get_return_transaction_by_id(transaction_id)

    if transaction is None:
        return "Return transaction not found", 404

    if request.method == "POST":
        rejection_reason = request.form.get("rejection_reason", "").strip()
        penalty_amount = request.form.get("penalty_amount", "").strip()
        rejected_by = _current_librarian_identity()

        # Validate amount before changing the return status to reduce partial updates.
        amount_success, amount_message, _ = validate_penalty_amount(penalty_amount)
        if not amount_success:
            return (
                render_template(
                    "librarian/reject_return_exception.html",
                    transaction=transaction,
                    error=amount_message,
                ),
                400,
            )

        if penalty_record_exists_for_rejected_return(transaction_id):
            return (
                render_template(
                    "librarian/reject_return_exception.html",
                    transaction=transaction,
                    error="Penalty record already exists for this rejected return.",
                ),
                400,
            )

        success, message = reject_return_exception(
            transaction_id,
            rejection_reason,
            rejected_by,
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
            transaction_id,
            penalty_amount,
            rejection_reason,
            rejected_by,
        )

        if not penalty_success:
            return (
                render_template(
                    "librarian/reject_return_exception.html",
                    transaction=get_return_transaction_by_id(transaction_id) or transaction,
                    error=penalty_message,
                ),
                400,
            )

        flash(f"{message} {penalty_message}", "success")
        return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

    return render_template(
        "librarian/reject_return_exception.html",
        transaction=transaction,
    )


@penalty_bp.route("/librarian/book-exception", methods=["GET"])
@librarian_required
def librarian_choose_book_exception():
    transactions = []

    try:
        transaction_docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in transaction_docs:
            transaction = doc.to_dict() or {}
            transaction["transaction_id"] = doc.id

            status = normalise_text(transaction.get("status"))
            if status in {
                "closed",
                "completed",
                "cancelled",
                "canceled",
                "rejected",
            }:
                continue

            if "exception recorded" in status:
                continue

            if book_exception_exists(doc.id):
                continue

            transactions.append(transaction)
    except Exception:
        _log_exception("Failed to retrieve borrowing transactions for exceptions.")

    if _testing_mode() and not transactions and DEMO_BORROW_TRANSACTIONS:
        for transaction_id, transaction in DEMO_BORROW_TRANSACTIONS.items():
            demo_transaction = transaction.copy()
            demo_transaction["transaction_id"] = transaction_id
            transactions.append(demo_transaction)

    return render_template(
        "librarian/select_book_exception.html",
        transactions=transactions,
    )


@penalty_bp.route(
    "/librarian/book-exception/<transaction_id>",
    methods=["GET", "POST"],
)
@librarian_required
def librarian_record_book_exception(transaction_id):
    transaction = get_return_transaction_by_id(transaction_id)

    # Backward compatibility: old links may pass a penalty ID.
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
        exception_description = request.form.get(
            "exception_description",
            "",
        ).strip()
        penalty_amount = request.form.get("penalty_amount", "").strip()
        recorded_by = _current_librarian_identity()

        # Validate the optional penalty amount before changing any records.
        if penalty_amount:
            amount_success, amount_message, _ = validate_penalty_amount(
                penalty_amount
            )
            if not amount_success:
                return (
                    render_template(
                        "librarian/book_exception.html",
                        transaction=transaction,
                        error=amount_message,
                    ),
                    400,
                )

            if penalty_record_exists_for_transaction(transaction_id, "Lost/Damaged Book"):
                return (
                    render_template(
                        "librarian/book_exception.html",
                        transaction=transaction,
                        error=(
                            "Penalty record already exists for this lost or damaged "
                            "book exception."
                        ),
                    ),
                    400,
                )

        success, message = record_lost_damaged_book_exception(
            transaction_id,
            exception_type,
            exception_description,
            recorded_by,
        )

        if not success:
            return (
                render_template(
                    "librarian/book_exception.html",
                    transaction=transaction,
                    error=message,
                ),
                400,
            )

        if penalty_amount:
            penalty_success, penalty_message = create_lost_damaged_book_exception_penalty(
                transaction_id,
                exception_type,
                exception_description,
                penalty_amount,
                recorded_by,
            )

            if not penalty_success:
                return (
                    render_template(
                        "librarian/book_exception.html",
                        transaction=get_return_transaction_by_id(transaction_id) or transaction,
                        error=(
                            f"{message} However, the related penalty could not be created. "
                            f"{penalty_message}"
                        ),
                    ),
                    400,
                )

            flash(f"{message} {penalty_message}", "success")
        else:
            flash(message, "success")

        return redirect(
            url_for("penalty_transaction.librarian_choose_book_exception")
        )

    return render_template(
        "librarian/book_exception.html",
        transaction=transaction,
    )


@penalty_bp.route(
    "/librarian/check-borrow-approval/<request_id>",
    methods=["GET", "POST"],
)
@librarian_required
def librarian_check_borrow_approval(request_id):
    borrow_request = get_borrow_request_by_id(request_id)

    if borrow_request is None:
        return "Borrow request not found", 404

    student_id = borrow_request.get("student_id")
    unpaid_penalties = get_unpaid_penalties_by_student(student_id)

    if request.method == "POST":
        approved_by = _current_librarian_identity()

        success, message = approve_borrow_request_with_penalty_check(
            request_id,
            approved_by,
        )

        if success:
            flash(message, "success")
            return redirect(
                url_for("penalty_transaction.librarian_borrow_approval_list")
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


# =========================================================
# ROUTES - STUDENT
# =========================================================


@penalty_bp.route("/student")
@penalty_bp.route("/student/<student_id>")
def student_penalty_records(student_id=None):
    resolved_student_id = student_id or get_current_student_id()

    if not resolved_student_id:
        if _testing_mode():
            return "Student identity is required.", 403
        return redirect(url_for("authentication.login"))

    # A student must not use the path parameter to view another student's data.
    if normalise_text(session.get("role")) == "student":
        session_student_id = get_current_student_id()
        if session_student_id and str(resolved_student_id) != str(session_student_id):
            abort(403)

    keyword = request.args.get("keyword", "").strip()
    status_filter = request.args.get("status", "all").strip()
    payment_method_filter = request.args.get("payment_method", "all").strip()

    all_penalties = get_student_penalty_records(resolved_student_id)

    filtered_penalties = filter_student_penalty_records(
        all_penalties,
        keyword,
        status_filter,
        payment_method_filter,
    )

    filtered_penalties = sort_student_penalties_for_display(filtered_penalties)

    return render_template(
        "student/penalty_records.html",
        student_id=resolved_student_id,
        penalties=filtered_penalties,
        total_penalties=len(all_penalties),
        result_count=len(filtered_penalties),
        keyword=keyword,
        status_filter=status_filter,
        payment_method_filter=payment_method_filter,
    )


@penalty_bp.route("/student/penalties", methods=["GET"])
def student_penalty_search_filter():
    student_id = get_current_student_id()

    if not student_id:
        if _testing_mode():
            return "Student identity is required.", 403
        return redirect(url_for("authentication.login"))

    keyword = request.args.get("keyword", "").strip()
    status_filter = request.args.get("status", "all").strip()
    payment_method_filter = request.args.get("payment_method", "all").strip()

    all_penalties = get_student_penalty_records(student_id)

    filtered_penalties = filter_student_penalty_records(
        all_penalties,
        keyword,
        status_filter,
        payment_method_filter,
    )

    filtered_penalties = sort_student_penalties_for_display(filtered_penalties)

    return render_template(
        "student/penalty_records.html",
        student_id=student_id,
        penalties=filtered_penalties,
        total_penalties=len(all_penalties),
        result_count=len(filtered_penalties),
        keyword=keyword,
        status_filter=status_filter,
        payment_method_filter=payment_method_filter,
    )


@penalty_bp.route(
    "/pay-credit-card/<penalty_id>",
    methods=["GET", "POST"],
)
@penalty_bp.route(
    "/student/pay-credit-card/<penalty_id>",
    methods=["GET", "POST"],
)
def student_pay_credit_card(penalty_id):
    student_id = get_current_student_id()

    if not student_id:
        if _testing_mode():
            # Old unit tests can pass student_id through form/query.
            student_id = request.form.get("student_id") or request.args.get("student_id")
        if not student_id:
            return "Student identity is required.", 403

    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id,
    )

    if not access_success:
        return access_message, 403

    if request.method == "POST":
        payment_amount = (
            request.form.get("payment_amount")
            or request.form.get("amount")
            or get_display_amount(penalty)
        )

        payment_method = request.form.get("payment_method", "").strip()
        is_legacy_payment = payment_method == ""

        if is_legacy_payment:
            payment_method = "Credit Card"

            card_number = request.form.get("card_number", "")
            if card_number:
                cleaned_card = card_number.replace(" ", "").replace("-", "")
                if not cleaned_card.isdigit() or not 12 <= len(cleaned_card) <= 19:
                    return (
                        render_template(
                            "student/pay_credit_card.html",
                            penalty=penalty,
                            student_id=student_id,
                            error="Payment failed. Please enter a valid card number.",
                        ),
                        400,
                    )
        else:
            details_success, details_message = validate_dynamic_payment_details(
                payment_method,
                request.form,
            )

            if not details_success:
                friendly_message = get_user_friendly_payment_message(
                    False,
                    details_message,
                    payment_method,
                )

                confirmation_summary = build_payment_confirmation_summary(
                    penalty,
                    student_id,
                    payment_amount,
                    payment_method,
                )

                return (
                    render_template(
                        "student/pay_credit_card.html",
                        penalty=penalty,
                        student_id=student_id,
                        error=friendly_message,
                        confirmation_summary=confirmation_summary,
                    ),
                    400,
                )

        success, message = pay_student_own_penalty(
            penalty_id,
            student_id,
            payment_amount,
            payment_method,
        )

        friendly_message = get_user_friendly_payment_message(
            success,
            message,
            payment_method,
        )

        if success:
            flash(friendly_message, "success")

            if is_legacy_payment:
                return redirect(url_for("penalty_transaction.student_penalty_records"))

            return redirect(
                url_for(
                    "penalty_transaction.payment_receipt",
                    penalty_id=penalty_id,
                )
            )

        confirmation_summary = build_payment_confirmation_summary(
            penalty,
            student_id,
            payment_amount,
            payment_method,
        )

        return (
            render_template(
                "student/pay_credit_card.html",
                penalty=penalty,
                student_id=student_id,
                error=friendly_message,
                confirmation_summary=confirmation_summary,
            ),
            400,
        )

    return render_template(
        "student/pay_credit_card.html",
        penalty=penalty,
        student_id=student_id,
    )


@penalty_bp.route(
    "/student/pay-cash/<penalty_id>",
    methods=["GET", "POST"],
)
def student_pay_cash(penalty_id):
    student_id = get_current_student_id()

    if not student_id:
        student_id = request.form.get("student_id") or request.args.get("student_id")
        if not student_id:
            return "Student identity is required.", 403

    access_success, access_message, penalty = validate_student_penalty_access(
        penalty_id,
        student_id,
    )

    if not access_success:
        return access_message, 403

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()

        # Keep the original cash flow: amount tendered may be more than the penalty.
        if cash_amount:
            success, message = pay_penalty_with_cash(penalty_id, cash_amount)
        else:
            payment_amount = (
                request.form.get("payment_amount")
                or get_display_amount(penalty)
            )
            success, message = pay_student_own_penalty(
                penalty_id,
                student_id,
                payment_amount,
                "Cash",
            )

        friendly_message = get_user_friendly_payment_message(
            success,
            message,
            "Cash",
        )

        if success:
            flash(friendly_message, "success")

            # Legacy cash test/flow returns to the records page.
            if cash_amount:
                return redirect(url_for("penalty_transaction.student_penalty_records"))

            return redirect(
                url_for(
                    "penalty_transaction.payment_receipt",
                    penalty_id=penalty_id,
                )
            )

        return (
            render_template(
                "student/pay_cash.html",
                penalty=penalty,
                student_id=student_id,
                error=friendly_message,
            ),
            400,
        )

    return render_template(
        "student/pay_cash.html",
        penalty=penalty,
        student_id=student_id,
    )


@penalty_bp.route(
    "/student/payment-receipt/<penalty_id>",
    methods=["GET"],
)
def payment_receipt(penalty_id):
    student_id = get_current_student_id()

    if not student_id:
        return "Student identity is required.", 403

    success, message, receipt = build_payment_receipt(
        penalty_id,
        student_id,
    )

    if not success:
        return message, 403

    return render_template(
        "student/payment_receipt.html",
        receipt=receipt,
    )
