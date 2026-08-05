"""Business rules for dashboard summaries."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

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
