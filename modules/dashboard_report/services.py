"""Business rules for dashboard summaries."""

from datetime import date, datetime, timedelta
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
