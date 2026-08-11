"""Business rules for dashboard summaries."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import csv
from io import StringIO

from modules.dashboard_report import repository

ACTIVE_BORROWING_STATUSES = {
    "active",
    "approved",
    "borrowed",
    "issued",
    "return pending",
}

ACTIVE_RESERVATION_STATUSES = {
    "active",
    "pending",
    "approved",
    "ready for collection",
    "borrow request submitted",
}

PENDING_BORROW_REQUEST_STATUSES = {
    "pending",
    "pending approval",
    "processing",
}

OUTSTANDING_PENALTY_STATUSES = {
    "outstanding",
    "pending",
    "unpaid",
}


def empty_student_summary():
    """Return the safe default values used when no records are available."""
    return {
        "active_borrowings": 0,
        "active_reservations": 0,
        "pending_borrow_requests": 0,
        "overdue_items": 0,
        "outstanding_penalties": 0,
        "outstanding_penalty_amount": 0.0,
    }


def _normalise_status(value):
    return " ".join(
        str(value or "")
        .strip()
        .lower()
        .replace("_", " ")
        .split()
    )


def _to_date(value):
    """Convert supported Firestore or string date values into a date."""
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    # Handles ISO dates, ISO datetimes and values ending in Z.
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    for date_format in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue

    return None


def _penalty_amount(penalty):
    raw_amount = penalty.get("penalty_amount", penalty.get("amount", 0))

    try:
        return Decimal(str(raw_amount or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def build_student_dashboard_summary(student_id, today=None):
    """Build a live dashboard summary for the authenticated student."""
    if not student_id or not str(student_id).strip():
        raise ValueError("A student ID is required to build the dashboard.")

    current_date = today or date.today()

    borrow_transactions = repository.get_student_borrow_transactions(student_id)
    reservations = repository.get_student_reservations(student_id)
    borrow_requests = repository.get_student_borrow_requests(student_id)
    penalties = repository.get_student_penalties(student_id)

    active_transactions = [
        transaction
        for transaction in borrow_transactions
        if _normalise_status(transaction.get("status"))
        in ACTIVE_BORROWING_STATUSES
    ]

    active_reservations = [
        reservation
        for reservation in reservations
        if _normalise_status(reservation.get("status"))
        in ACTIVE_RESERVATION_STATUSES
    ]

    pending_requests = [
        borrow_request
        for borrow_request in borrow_requests
        if _normalise_status(borrow_request.get("status"))
        in PENDING_BORROW_REQUEST_STATUSES
    ]

    outstanding_penalties = [
        penalty
        for penalty in penalties
        if _normalise_status(penalty.get("status"))
        in OUTSTANDING_PENALTY_STATUSES
    ]

    overdue_items = 0

    for transaction in active_transactions:
        due_date = _to_date(transaction.get("due_date"))

        if due_date is not None and due_date < current_date:
            overdue_items += 1

    total_penalty = sum(
        (_penalty_amount(penalty) for penalty in outstanding_penalties),
        Decimal("0"),
    )

    return {
        "active_borrowings": len(active_transactions),
        "active_reservations": len(active_reservations),
        "pending_borrow_requests": len(pending_requests),
        "overdue_items": overdue_items,
        "outstanding_penalties": len(outstanding_penalties),
        "outstanding_penalty_amount": float(total_penalty),
    }


APPROVED_RESERVATION_ALERT_STATUSES = {
    "approved",
    "ready for collection",
}


def empty_student_alerts():
    """Return a safe empty alert list for the student dashboard."""
    return []


def _book_title(record):
    """Resolve a readable book title without failing on missing related data."""
    stored_title = str(record.get("book_title", "")).strip()
    if stored_title:
        return stored_title

    book_id = str(record.get("book_id", "")).strip()
    if not book_id:
        return "Unknown Book"

    try:
        book = repository.get_book_by_id(book_id)
    except Exception:
        book = None

    if not book:
        return "Unknown Book"

    return str(book.get("title", "Unknown Book")).strip() or "Unknown Book"


def build_student_attention_alerts(
    student_id,
    today=None,
    due_soon_days=3,
):
    """Build unresolved student alerts for dashboard attention items.

    Alerts are read-only summaries. Existing borrowing, reservation, and
    penalty modules remain responsible for all state-changing actions.
    """
    if not student_id or not str(student_id).strip():
        raise ValueError("A student ID is required to build dashboard alerts.")

    if due_soon_days < 0:
        raise ValueError("The due-soon period cannot be negative.")

    current_date = today or date.today()
    due_soon_limit = current_date + timedelta(days=due_soon_days)
    alerts = []

    borrow_transactions = repository.get_student_borrow_transactions(student_id)
    reservations = repository.get_student_reservations(student_id)
    penalties = repository.get_student_penalties(student_id)

    for transaction in borrow_transactions:
        if (
            _normalise_status(transaction.get("status"))
            not in ACTIVE_BORROWING_STATUSES
        ):
            continue

        due_date = _to_date(transaction.get("due_date"))
        if due_date is None:
            continue

        title = _book_title(transaction)
        formatted_due_date = due_date.strftime("%d %b %Y")

        if due_date < current_date:
            overdue_days = (current_date - due_date).days
            alerts.append(
                {
                    "category": "Overdue Book",
                    "title": title,
                    "message": (
                        f"This book was due on {formatted_due_date} "
                        f"and is {overdue_days} day"
                        f"{'s' if overdue_days != 1 else ''} overdue."
                    ),
                    "severity": "danger",
                    "action_url": "/catalogue/my-borrowed-books",
                    "action_label": "View Borrowed Books",
                    "sort_order": 0,
                    "sort_date": due_date.isoformat(),
                }
            )
        elif current_date <= due_date <= due_soon_limit:
            remaining_days = (due_date - current_date).days
            if remaining_days == 0:
                timing = "due today"
            elif remaining_days == 1:
                timing = "due tomorrow"
            else:
                timing = f"due in {remaining_days} days"

            alerts.append(
                {
                    "category": "Due Soon",
                    "title": title,
                    "message": (
                        f"This book is {timing} on {formatted_due_date}."
                    ),
                    "severity": "warning",
                    "action_url": "/catalogue/my-borrowed-books",
                    "action_label": "View Borrowed Books",
                    "sort_order": 1,
                    "sort_date": due_date.isoformat(),
                }
            )

    for reservation in reservations:
        if (
            _normalise_status(reservation.get("status"))
            not in APPROVED_RESERVATION_ALERT_STATUSES
        ):
            continue

        title = _book_title(reservation)
        alerts.append(
            {
                "category": "Approved Reservation",
                "title": title,
                "message": (
                    "Your reservation is approved and can continue into "
                    "the borrowing process."
                ),
                "severity": "success",
                "action_url": "/catalogue/my-reservations",
                "action_label": "Continue Reservation",
                "sort_order": 2,
                "sort_date": str(reservation.get("reservation_date", "")),
            }
        )

    for penalty in penalties:
        if (
            _normalise_status(penalty.get("status"))
            not in OUTSTANDING_PENALTY_STATUSES
        ):
            continue

        amount = _penalty_amount(penalty)
        title = _book_title(penalty)
        penalty_reason = str(penalty.get("penalty_reason", "")).strip()
        reason_text = f" Reason: {penalty_reason}." if penalty_reason else ""

        alerts.append(
            {
                "category": "Outstanding Penalty",
                "title": title,
                "message": (
                    f"RM {float(amount):.2f} remains outstanding."
                    f"{reason_text}"
                ),
                "severity": "danger",
                "action_url": "/penalty/student",
                "action_label": "Review Penalty",
                "sort_order": 3,
                "sort_date": str(
                    penalty.get("created_date", penalty.get("created_at", ""))
                ),
            }
        )

    alerts.sort(
        key=lambda alert: (
            alert.get("sort_order", 99),
            alert.get("sort_date", ""),
            alert.get("title", "").lower(),
        )
    )

    return alerts



INACTIVE_ACCOUNT_STATUSES = {
    "inactive",
    "deactivated",
    "disabled",
    "suspended",
}


def empty_librarian_statistics():
    """Return safe zero values when librarian statistics cannot be loaded."""
    return {
        "active_students": 0,
        "total_book_titles": 0,
        "total_physical_copies": 0,
        "available_copies": 0,
        "active_borrowings": 0,
        "active_reservations": 0,
        "outstanding_penalties": 0,
        "outstanding_penalty_amount": 0.0,
    }


def _safe_nonnegative_int(value):
    """Convert stored numeric values safely for dashboard aggregation."""
    if isinstance(value, bool):
        return 0

    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _is_active_student(user):
    if _normalise_status(user.get("role")) != "student":
        return False

    account_status = _normalise_status(user.get("account_status"))
    return account_status not in INACTIVE_ACCOUNT_STATUSES


def build_librarian_dashboard_statistics():
    """Build read-only system-wide statistics for the librarian dashboard."""
    users = repository.get_all_users()
    books = repository.get_all_books()
    borrow_transactions = repository.get_all_borrow_transactions()
    reservations = repository.get_all_reservations()
    penalties = repository.get_all_penalties()

    active_students = sum(1 for user in users if _is_active_student(user))

    total_physical_copies = 0
    available_copies = 0

    for book in books:
        total_copies = _safe_nonnegative_int(book.get("total_copies"))
        current_available = _safe_nonnegative_int(book.get("available_copies"))

        total_physical_copies += total_copies
        if total_copies > 0:
            current_available = min(current_available, total_copies)
        available_copies += current_available

    active_borrowings = sum(
        1
        for transaction in borrow_transactions
        if _normalise_status(transaction.get("status"))
        in ACTIVE_BORROWING_STATUSES
    )

    active_reservations = sum(
        1
        for reservation in reservations
        if _normalise_status(reservation.get("status"))
        in ACTIVE_RESERVATION_STATUSES
    )

    outstanding_penalty_records = [
        penalty
        for penalty in penalties
        if _normalise_status(penalty.get("status"))
        in OUTSTANDING_PENALTY_STATUSES
    ]
    outstanding_penalty_amount = sum(
        (_penalty_amount(penalty) for penalty in outstanding_penalty_records),
        Decimal("0"),
    )

    return {
        "active_students": active_students,
        "total_book_titles": len(books),
        "total_physical_copies": total_physical_copies,
        "available_copies": available_copies,
        "active_borrowings": active_borrowings,
        "active_reservations": active_reservations,
        "outstanding_penalties": len(outstanding_penalty_records),
        "outstanding_penalty_amount": float(outstanding_penalty_amount),
    }


RETURN_REQUEST_STATUSES = {
    "return pending",
    "return requested",
}

PENDING_RENEWAL_STATUSES = {
    "pending",
    "pending approval",
}

UNRESOLVED_EXCEPTION_STATUSES = {
    "rejected",
    "exception pending",
    "exception recorded",
    "lost exception recorded",
    "damaged exception recorded",
}

RESOLVED_EXCEPTION_STATUSES = {
    "closed",
    "completed",
    "exception completed",
    "resolved",
}


def empty_librarian_pending_actions():
    """Return safe zero values for librarian action counts."""
    return {
        "pending_borrow_requests": 0,
        "pending_returns": 0,
        "pending_renewals": 0,
        "overdue_transactions": 0,
        "unresolved_exceptions": 0,
        "total_pending_actions": 0,
    }


def _has_unresolved_exception(transaction):
    """Identify exception records that still require librarian attention."""
    transaction_status = _normalise_status(transaction.get("status"))
    return_status = _normalise_status(transaction.get("return_status"))
    exception_status = _normalise_status(
        transaction.get(
            "book_exception_status",
            transaction.get("exception_status"),
        )
    )

    if transaction_status in RESOLVED_EXCEPTION_STATUSES:
        return False

    return any(
        value in UNRESOLVED_EXCEPTION_STATUSES
        for value in (
            transaction_status,
            return_status,
            exception_status,
        )
    )


def build_librarian_pending_actions(today=None):
    """Build read-only counts of operational work awaiting a librarian."""
    current_date = today or date.today()
    borrow_requests = repository.get_all_borrow_requests()
    borrow_transactions = repository.get_all_borrow_transactions()

    pending_borrow_requests = sum(
        1
        for request in borrow_requests
        if _normalise_status(request.get("status"))
        in PENDING_BORROW_REQUEST_STATUSES
    )

    pending_returns = sum(
        1
        for transaction in borrow_transactions
        if _normalise_status(transaction.get("status"))
        in RETURN_REQUEST_STATUSES
    )

    pending_renewals = sum(
        1
        for transaction in borrow_transactions
        if _normalise_status(transaction.get("renewal_status"))
        in PENDING_RENEWAL_STATUSES
    )

    overdue_transactions = 0
    for transaction in borrow_transactions:
        transaction_status = _normalise_status(transaction.get("status"))
        due_date = _to_date(transaction.get("due_date"))

        if (
            transaction_status in ACTIVE_BORROWING_STATUSES
            and due_date is not None
            and due_date < current_date
        ):
            overdue_transactions += 1

    unresolved_exceptions = sum(
        1
        for transaction in borrow_transactions
        if _has_unresolved_exception(transaction)
    )

    counts = {
        "pending_borrow_requests": pending_borrow_requests,
        "pending_returns": pending_returns,
        "pending_renewals": pending_renewals,
        "overdue_transactions": overdue_transactions,
        "unresolved_exceptions": unresolved_exceptions,
    }
    counts["total_pending_actions"] = sum(counts.values())
    return counts


OPERATIONAL_REPORT_TYPES = {
    "borrowing": "Borrowing Transactions",
    "reservation": "Reservation Activities",
    "penalty": "Penalty Transactions",
    "overdue": "Overdue Transactions",
}

OPERATIONAL_REPORT_STATUSES = {
    "borrowing": (
        "pending",
        "approved",
        "active",
        "borrowed",
        "issued",
        "return pending",
        "returned",
        "rejected",
        "closed",
        "exception completed",
    ),
    "reservation": (
        "active",
        "pending",
        "approved",
        "ready for collection",
        "borrow request submitted",
        "fulfilled",
        "cancelled",
    ),
    "penalty": (
        "outstanding",
        "pending",
        "unpaid",
        "paid",
        "waived",
        "cancelled",
    ),
    "overdue": tuple(sorted(ACTIVE_BORROWING_STATUSES)),
}


def get_operational_report_types():
    """Return report type values and labels for the librarian filter form."""
    return [
        {"value": value, "label": label}
        for value, label in OPERATIONAL_REPORT_TYPES.items()
    ]


def get_operational_report_statuses(report_type):
    """Return valid status options for one operational report type."""
    normalised_type = _normalise_status(report_type).replace(" ", "")
    if normalised_type not in OPERATIONAL_REPORT_TYPES:
        normalised_type = "borrowing"

    return [
        {
            "value": status,
            "label": status.title(),
        }
        for status in OPERATIONAL_REPORT_STATUSES[normalised_type]
    ]


def empty_operational_report_result(report_type="borrowing"):
    """Return a safe empty report result for rendering and error handling."""
    selected_type = str(report_type or "borrowing").strip().lower()
    if selected_type not in OPERATIONAL_REPORT_TYPES:
        selected_type = "borrowing"

    return {
        "report_type": selected_type,
        "report_title": OPERATIONAL_REPORT_TYPES[selected_type],
        "records": [],
        "total_records": 0,
        "status_totals": {},
    }


def _parse_report_filter_date(raw_value, field_label):
    if raw_value is None or str(raw_value).strip() == "":
        return None

    parsed_value = _to_date(raw_value)
    if parsed_value is None:
        raise ValueError(f"{field_label} must be a valid date.")

    return parsed_value


def _record_identifier(record, *candidate_fields):
    for field_name in candidate_fields:
        value = str(record.get(field_name, "")).strip()
        if value:
            return value
    return "Unknown"


def _build_identifier_lookup(records, candidate_fields):
    """Index related records by any supported identifier field."""
    lookup = {}

    for record in records:
        for field_name in candidate_fields:
            value = str(record.get(field_name, "")).strip()
            if value and value not in lookup:
                lookup[value] = record

    return lookup


def _display_report_date(value, empty_label="Unknown"):
    parsed_date = _to_date(value)
    if parsed_date is None:
        return empty_label
    return parsed_date.strftime("%d %b %Y")


def _build_borrowing_related_lookups():
    """Build safe student and book lookup tables for detailed reports."""
    student_lookup = _build_identifier_lookup(
        repository.get_all_users(),
        ("document_id", "user_id", "student_id", "id"),
    )
    book_lookup = _build_identifier_lookup(
        repository.get_all_books(),
        ("document_id", "book_id", "id"),
    )
    return student_lookup, book_lookup


def _detailed_borrowing_fields(
    record,
    student_lookup,
    book_lookup,
    current_date,
):
    """Return display fields required by SCRUM-1538."""
    student_id = str(record.get("student_id", "")).strip()
    book_id = str(record.get("book_id", "")).strip()

    student = student_lookup.get(student_id, {})
    book = book_lookup.get(book_id, {})

    student_name = str(student.get("full_name", "")).strip() or "Unknown Student"
    book_title = (
        str(record.get("book_title", "")).strip()
        or str(book.get("title", "")).strip()
        or "Unknown Book"
    )

    due_date = _to_date(record.get("due_date"))
    record_status = _normalise_status(record.get("status"))
    is_overdue = bool(
        due_date is not None
        and due_date < current_date
        and record_status in ACTIVE_BORROWING_STATUSES
    )

    overdue_days = (current_date - due_date).days if is_overdue else 0

    return {
        "student_name": student_name,
        "book_title": book_title,
        "borrow_date_display": _display_report_date(record.get("borrow_date")),
        "due_date_display": _display_report_date(record.get("due_date")),
        "return_date_display": _display_report_date(
            record.get("return_date"),
            empty_label="Not returned",
        ),
        "renewal_status": str(record.get("renewal_status", "None")).strip() or "None",
        "is_overdue": is_overdue,
        "overdue_days": overdue_days,
    }


def _build_reservation_related_lookups():
    """Build student, book, and borrowing-request lookups for reservations."""
    student_lookup = _build_identifier_lookup(
        repository.get_all_users(),
        ("document_id", "user_id", "student_id", "id"),
    )
    book_lookup = _build_identifier_lookup(
        repository.get_all_books(),
        ("document_id", "book_id", "id"),
    )

    borrow_requests = repository.get_all_borrow_requests()
    request_lookup = _build_identifier_lookup(
        borrow_requests,
        ("document_id", "request_id", "id"),
    )
    request_by_reservation = {}
    for borrow_request in borrow_requests:
        reservation_id = str(
            borrow_request.get("reservation_id", "")
        ).strip()
        if reservation_id and reservation_id not in request_by_reservation:
            request_by_reservation[reservation_id] = borrow_request

    return (
        student_lookup,
        book_lookup,
        request_lookup,
        request_by_reservation,
    )


def _reservation_activity_fields(
    record,
    student_lookup,
    book_lookup,
    request_lookup,
    request_by_reservation,
):
    """Return detailed reservation and linked borrowing-request fields."""
    reservation_id = _operational_record_id("reservation", record)
    student_id = str(record.get("student_id", "")).strip()
    book_id = str(record.get("book_id", "")).strip()

    student = student_lookup.get(student_id, {})
    book = book_lookup.get(book_id, {})

    student_name = (
        str(student.get("full_name", "")).strip()
        or str(student.get("name", "")).strip()
        or "Unknown Student"
    )
    book_title = (
        str(record.get("book_title", "")).strip()
        or str(book.get("title", "")).strip()
        or "Unknown Book"
    )

    borrowing_request_id = str(
        record.get("borrowing_request_id", "")
    ).strip()
    borrow_request = None
    if borrowing_request_id:
        borrow_request = request_lookup.get(borrowing_request_id)
    if borrow_request is None:
        borrow_request = request_by_reservation.get(reservation_id)

    if borrow_request is not None:
        borrowing_request_id = _record_identifier(
            borrow_request,
            "request_id",
            "document_id",
            "id",
        )
        borrowing_request_status = (
            str(borrow_request.get("status", "Unknown")).strip() or "Unknown"
        )
    elif borrowing_request_id:
        borrowing_request_status = "Not Found"
    else:
        borrowing_request_id = "Not submitted"
        borrowing_request_status = "Not submitted"

    return {
        "student_name": student_name,
        "book_title": book_title,
        "reservation_date_display": _display_report_date(
            record.get("reservation_date") or record.get("created_at")
        ),
        "borrowing_request_id": borrowing_request_id,
        "borrowing_request_status": borrowing_request_status,
    }


def _reservation_demand_summary(records):
    """Return reservation counts by book, highest demand first."""
    demand = {}

    for record in records:
        book_id = str(record.get("book_id", "Unknown")).strip() or "Unknown"
        book_title = (
            str(record.get("book_title", "Unknown Book")).strip()
            or "Unknown Book"
        )
        key = (book_id, book_title)
        demand[key] = demand.get(key, 0) + 1

    ranked = [
        {
            "book_id": book_id,
            "book_title": book_title,
            "reservation_count": count,
        }
        for (book_id, book_title), count in demand.items()
    ]
    ranked.sort(
        key=lambda item: (
            -item["reservation_count"],
            item["book_title"].lower(),
            item["book_id"],
        )
    )
    return ranked


def _build_penalty_transaction_lookup(penalties):
    """Group penalty records by borrowing transaction for overdue reporting."""
    lookup = {}

    for penalty in penalties:
        transaction_id = str(penalty.get("transaction_id", "")).strip()
        if not transaction_id:
            continue
        lookup.setdefault(transaction_id, []).append(penalty)

    return lookup


def _select_overdue_penalty(penalties):
    """Prefer a linked overdue penalty while remaining safe with legacy data."""
    if not penalties:
        return None

    def penalty_priority(penalty):
        text = " ".join(
            [
                str(penalty.get("penalty_type", "")),
                str(penalty.get("penalty_reason", "")),
            ]
        ).lower()
        is_overdue_penalty = "overdue" in text
        status = _normalise_status(penalty.get("status"))
        active_priority = 0 if status in OUTSTANDING_PENALTY_STATUSES else 1
        return (0 if is_overdue_penalty else 1, active_priority)

    return sorted(penalties, key=penalty_priority)[0]


def _derived_payment_status(penalty):
    explicit_status = str(penalty.get("payment_status", "")).strip()
    if explicit_status:
        return explicit_status

    status = _normalise_status(penalty.get("status"))
    if status == "paid":
        return "Paid"
    if status == "waived":
        return "Not Applicable"
    if status in OUTSTANDING_PENALTY_STATUSES:
        return "Unpaid"
    if status == "cancelled":
        return "Cancelled"
    return "Not Recorded"


def _overdue_penalty_fields(
    record,
    student_lookup,
    book_lookup,
    penalty_lookup,
    current_date,
):
    """Return joined overdue, student, book and penalty details for SCRUM-1539."""
    details = _detailed_borrowing_fields(
        record,
        student_lookup,
        book_lookup,
        current_date,
    )

    transaction_id = _operational_record_id("overdue", record)
    penalty = _select_overdue_penalty(penalty_lookup.get(transaction_id, []))

    if penalty is None:
        details.update(
            {
                "penalty_id": "Not recorded",
                "penalty_amount": None,
                "penalty_status": "Not Recorded",
                "payment_status": "Not Recorded",
                "payment_method": "Not recorded",
                "waiver_status": "Not Waived",
                "waiver_reason": "Not recorded",
            }
        )
        return details

    penalty_status = str(penalty.get("status", "Unknown")).strip() or "Unknown"
    waiver_reason = str(penalty.get("waiver_reason", "")).strip()
    is_waived = _normalise_status(penalty_status) == "waived" or bool(waiver_reason)

    details.update(
        {
            "penalty_id": _record_identifier(
                penalty,
                "penalty_id",
                "document_id",
                "id",
            ),
            "penalty_amount": float(_penalty_amount(penalty)),
            "penalty_status": penalty_status,
            "payment_status": _derived_payment_status(penalty),
            "payment_method": str(
                penalty.get("payment_method", "Not recorded")
            ).strip()
            or "Not recorded",
            "waiver_status": "Waived" if is_waived else "Not Waived",
            "waiver_reason": waiver_reason or "Not recorded",
        }
    )
    return details


def _operational_event_date(report_type, record):
    field_candidates = {
        "borrowing": (
            "borrow_date",
            "request_date",
            "created_at",
        ),
        "reservation": (
            "reservation_date",
            "created_at",
            "updated_at",
        ),
        "penalty": (
            "created_date",
            "created_at",
            "payment_date",
            "updated_at",
        ),
        "overdue": ("due_date",),
    }

    for field_name in field_candidates[report_type]:
        parsed_date = _to_date(record.get(field_name))
        if parsed_date is not None:
            return parsed_date

    return None


def _operational_record_id(report_type, record):
    candidates = {
        "borrowing": (
            "transaction_id",
            "request_id",
            "document_id",
            "id",
        ),
        "reservation": (
            "reservation_id",
            "document_id",
            "id",
        ),
        "penalty": (
            "penalty_id",
            "document_id",
            "id",
        ),
        "overdue": (
            "transaction_id",
            "document_id",
            "id",
        ),
    }
    return _record_identifier(record, *candidates[report_type])


def _operational_summary(report_type, record, current_date):
    if report_type == "borrowing":
        return "Borrowing transaction"

    if report_type == "reservation":
        return "Reservation activity"

    if report_type == "penalty":
        penalty_type = str(record.get("penalty_type", "")).strip()
        penalty_reason = str(record.get("penalty_reason", "")).strip()
        return penalty_type or penalty_reason or "Penalty transaction"

    due_date = _to_date(record.get("due_date"))
    if due_date is None:
        return "Overdue borrowing transaction"

    overdue_days = max((current_date - due_date).days, 0)
    return (
        f"Overdue by {overdue_days} day"
        f"{'s' if overdue_days != 1 else ''}"
    )


def _operational_source_records(report_type):
    if report_type in {"borrowing", "overdue"}:
        return repository.get_all_borrow_transactions()
    if report_type == "reservation":
        return repository.get_all_reservations()
    return repository.get_all_penalties()


def build_operational_report(
    report_type="borrowing",
    start_date=None,
    end_date=None,
    status=None,
    book_title=None,
    today=None,
):
    """Generate a read-only operational report using validated filters."""
    selected_type = str(report_type or "").strip().lower()
    if selected_type not in OPERATIONAL_REPORT_TYPES:
        raise ValueError("Please select a supported report type.")

    parsed_start_date = _parse_report_filter_date(start_date, "Start date")
    parsed_end_date = _parse_report_filter_date(end_date, "End date")

    if (
        parsed_start_date is not None
        and parsed_end_date is not None
        and parsed_start_date > parsed_end_date
    ):
        raise ValueError("Start date cannot be later than end date.")

    selected_status = _normalise_status(status)
    allowed_statuses = set(OPERATIONAL_REPORT_STATUSES[selected_type])
    if selected_status and selected_status not in allowed_statuses:
        raise ValueError("Please select a valid status for this report type.")

    selected_book_title = str(book_title or "").strip().lower()

    current_date = today or date.today()
    report_records = []
    student_lookup = {}
    book_lookup = {}
    penalty_lookup = {}
    reservation_request_lookup = {}
    reservation_request_by_reservation = {}

    if selected_type in {"borrowing", "overdue"}:
        student_lookup, book_lookup = _build_borrowing_related_lookups()

    if selected_type == "reservation":
        (
            student_lookup,
            book_lookup,
            reservation_request_lookup,
            reservation_request_by_reservation,
        ) = _build_reservation_related_lookups()

    if selected_type == "overdue":
        penalty_lookup = _build_penalty_transaction_lookup(
            repository.get_all_penalties()
        )

    for record in _operational_source_records(selected_type):
        record_status = _normalise_status(record.get("status"))
        event_date = _operational_event_date(selected_type, record)

        if selected_type == "overdue":
            if (
                record_status not in ACTIVE_BORROWING_STATUSES
                or event_date is None
                or event_date >= current_date
            ):
                continue

        if selected_status and record_status != selected_status:
            continue

        if parsed_start_date is not None:
            if event_date is None or event_date < parsed_start_date:
                continue

        if parsed_end_date is not None:
            if event_date is None or event_date > parsed_end_date:
                continue

        report_record = {
            "record_id": _operational_record_id(selected_type, record),
            "event_date": (
                event_date.isoformat() if event_date is not None else ""
            ),
            "event_date_display": (
                event_date.strftime("%d %b %Y")
                if event_date is not None
                else "Unknown"
            ),
            "status": str(record.get("status", "Unknown")).strip()
            or "Unknown",
            "student_id": str(record.get("student_id", "Unknown")).strip()
            or "Unknown",
            "book_id": str(record.get("book_id", "Unknown")).strip()
            or "Unknown",
            "summary": _operational_summary(
                selected_type,
                record,
                current_date,
            ),
            "amount": (
                float(_penalty_amount(record))
                if selected_type == "penalty"
                else None
            ),
        }

        if selected_type == "borrowing":
            report_record.update(
                _detailed_borrowing_fields(
                    record,
                    student_lookup,
                    book_lookup,
                    current_date,
                )
            )
        elif selected_type == "reservation":
            report_record.update(
                _reservation_activity_fields(
                    record,
                    student_lookup,
                    book_lookup,
                    reservation_request_lookup,
                    reservation_request_by_reservation,
                )
            )
            if (
                selected_book_title
                and selected_book_title
                not in report_record["book_title"].lower()
            ):
                continue
        elif selected_type == "overdue":
            report_record.update(
                _overdue_penalty_fields(
                    record,
                    student_lookup,
                    book_lookup,
                    penalty_lookup,
                    current_date,
                )
            )

        report_records.append(report_record)

    report_records.sort(
        key=lambda item: (
            item.get("event_date", ""),
            item.get("record_id", ""),
        ),
        reverse=True,
    )

    status_totals = {}
    for record in report_records:
        status_label = record["status"]
        status_totals[status_label] = status_totals.get(status_label, 0) + 1

    result = {
        "report_type": selected_type,
        "report_title": OPERATIONAL_REPORT_TYPES[selected_type],
        "records": report_records,
        "total_records": len(report_records),
        "status_totals": status_totals,
    }

    if selected_type == "reservation":
        result["book_demand"] = _reservation_demand_summary(report_records)
        result["most_requested_books"] = result["book_demand"][:5]
    elif selected_type == "borrowing":
        result["overdue_count"] = sum(
            1 for record in report_records if record.get("is_overdue")
        )
    elif selected_type == "overdue":
        result["total_penalty_amount"] = sum(
            record.get("penalty_amount") or 0.0
            for record in report_records
        )
        penalty_status_totals = {}
        for record in report_records:
            penalty_status = record.get("penalty_status", "Not Recorded")
            penalty_status_totals[penalty_status] = (
                penalty_status_totals.get(penalty_status, 0) + 1
            )
        result["penalty_status_totals"] = penalty_status_totals

    return result


# SCRUM-1540: Export the currently filtered operational report to CSV.
REPORT_EXPORT_COLUMNS = {
    "borrowing": (
        ("Transaction ID", "record_id"),
        ("Student Name", "student_name"),
        ("Student ID", "student_id"),
        ("Book Title", "book_title"),
        ("Book ID", "book_id"),
        ("Borrow Date", "borrow_date_display"),
        ("Due Date", "due_date_display"),
        ("Return Date", "return_date_display"),
        ("Renewal Status", "renewal_status"),
        ("Transaction Status", "status"),
    ),
    "reservation": (
        ("Reservation ID", "record_id"),
        ("Student Name", "student_name"),
        ("Student ID", "student_id"),
        ("Book Title", "book_title"),
        ("Book ID", "book_id"),
        ("Reservation Date", "reservation_date_display"),
        ("Reservation Status", "status"),
        ("Borrow Request ID", "borrowing_request_id"),
        ("Borrow Request Status", "borrowing_request_status"),
    ),
    "penalty": (
        ("Penalty ID", "record_id"),
        ("Penalty Date", "event_date_display"),
        ("Penalty Status", "status"),
        ("Student ID", "student_id"),
        ("Book ID", "book_id"),
        ("Details", "summary"),
        ("Amount (RM)", "amount"),
    ),
    "overdue": (
        ("Transaction ID", "record_id"),
        ("Student Name", "student_name"),
        ("Student ID", "student_id"),
        ("Book Title", "book_title"),
        ("Book ID", "book_id"),
        ("Due Date", "due_date_display"),
        ("Overdue Days", "overdue_days"),
        ("Transaction Status", "status"),
        ("Penalty ID", "penalty_id"),
        ("Penalty Amount (RM)", "penalty_amount"),
        ("Penalty Status", "penalty_status"),
        ("Payment Status", "payment_status"),
        ("Payment Method", "payment_method"),
        ("Waiver Status", "waiver_status"),
        ("Waiver Reason", "waiver_reason"),
    ),
}


def _csv_safe_value(value):
    """Return a CSV-safe value and prevent spreadsheet formula execution."""
    if value is None:
        return ""

    if isinstance(value, float):
        return f"{value:.2f}"

    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def build_operational_report_csv(report):
    """Serialize a generated report using an explicit non-sensitive schema."""
    report_type = str(report.get("report_type", "")).strip().lower()
    columns = REPORT_EXPORT_COLUMNS.get(report_type)
    if columns is None:
        raise ValueError("Please select a supported report type for export.")

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([heading for heading, _field in columns])

    for record in report.get("records", []):
        writer.writerow(
            [
                _csv_safe_value(record.get(field_name))
                for _heading, field_name in columns
            ]
        )

    return output.getvalue()


def build_operational_report_filename(report_type, export_date=None):
    """Create a predictable filename without student or sensitive values."""
    selected_type = str(report_type or "").strip().lower()
    if selected_type not in REPORT_EXPORT_COLUMNS:
        raise ValueError("Please select a supported report type for export.")

    current_date = export_date or date.today()
    return f"{selected_type}_report_{current_date.isoformat()}.csv"
