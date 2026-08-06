from modules.borrowing.repository import (
    add_borrow_transaction,
    delete_borrow_transaction,
    find_request,
    find_borrow_transaction,
    find_reservation,
    get_borrow_transactions,
    get_pending_requests,
    find_book,
    has_active_reservation,
    update_book,
    update_borrow_transaction,
    update_request_status,
    update_reservation,
    has_outstanding_penalty,
    has_active_borrow_transaction,
)

from datetime import date, datetime, timedelta


def get_book_title(book_id: str) -> str:

    book = find_book(book_id)

    if book:
        return book.get("title", "Unknown Book")

    return "Unknown Book"


# Route for Librarians
def get_all_pending_requests():
    return get_pending_requests()


def get_pending_requests_with_validation():

    requests = get_pending_requests()

    for borrow_request in requests:

        borrow_request["approval_error"] = get_borrow_approval_error(
            borrow_request["id"]
        )

    return requests


def get_all_borrow_transactions():
    return get_borrow_transactions()


# Route for Students
def get_student_borrowed_books(student_id):

    books = []

    for transaction in get_borrow_transactions():

        if transaction["student_id"] == student_id:

            book = find_book(transaction["book_id"])

            transaction["book_title"] = book["title"]

            books.append(transaction)

    return books


def _normalise_status(value):
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _book_can_be_issued(book):
    """Return True only when the aggregate catalogue record is available."""
    if book is None:
        return False

    try:
        available_copies = int(book.get("available_copies", 0))
    except (TypeError, ValueError):
        available_copies = 0

    if available_copies <= 0:
        return False

    stored_status = _normalise_status(book.get("status"))
    return not stored_status or stored_status == "available"


def approve_borrow_request(request_id: str):
    """Approve a pending request and synchronise related records.

    The approval checks penalties, availability, duplicate active borrowing,
    and an optional linked reservation. If a later database operation fails,
    earlier updates are restored where possible.
    """
    borrow_request = find_request(request_id)

    if borrow_request is None:
        return False

    if _normalise_status(borrow_request.get("status")) != "pending":
        return False

    student_id = borrow_request.get("student_id")
    book_id = borrow_request.get("book_id")

    if not student_id or not book_id:
        return False

    if has_outstanding_penalty(student_id):
        return False

    book = find_book(book_id)

    if not _book_can_be_issued(book):
        return False

    if has_active_borrow_transaction(student_id, book_id):
        return False

    reservation_id = borrow_request.get("reservation_id")
    reservation = find_reservation(reservation_id) if reservation_id else None

    original_request_status = borrow_request.get(
        "status",
        "Pending",
    )

    original_book_values = {
        "available_copies": book.get("available_copies", 0),
        "status": book.get("status"),
        "updated_at": book.get("updated_at"),
    }

    original_reservation_values = None

    if reservation is not None:
        original_reservation_values = {
            "status": reservation.get("status"),
            "borrowing_request_id": reservation.get("borrowing_request_id"),
            "borrowing_transaction_id": reservation.get("borrowing_transaction_id"),
            "fulfilled_at": reservation.get("fulfilled_at"),
        }

    try:
        available_copies = int(book.get("available_copies", 0))
    except (TypeError, ValueError):
        return False

    remaining_copies = available_copies - 1
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    transaction_id = None

    try:
        update_book(
            book_id,
            {
                "available_copies": remaining_copies,
                "status": ("Available" if remaining_copies > 0 else "Unavailable"),
                "updated_at": current_time,
            },
        )

        update_request_status(
            request_id,
            "Approved",
        )

        borrow_date = date.today()
        due_date = borrow_date + timedelta(days=14)

        transaction = {
            "request_id": request_id,
            "book_id": book_id,
            "student_id": student_id,
            "borrow_date": borrow_date.isoformat(),
            "due_date": due_date.isoformat(),
            "return_date": None,
            "status": "Borrowed",
            "renewal_status": "None",
            "show_renewal_message": False,
            "renewal_message": "",
        }

        if reservation_id:
            transaction["reservation_id"] = reservation_id

        transaction_id = add_borrow_transaction(transaction)

        if reservation_id:
            if reservation is None:
                raise ValueError("Linked reservation was not found.")

            update_reservation(
                reservation_id,
                {
                    "status": "Fulfilled",
                    "borrowing_request_id": request_id,
                    "borrowing_transaction_id": (transaction_id),
                    "fulfilled_at": current_time,
                },
            )

        return transaction_id

    except Exception:
        if transaction_id:
            try:
                delete_borrow_transaction(transaction_id)
            except Exception:
                pass

        try:
            update_request_status(
                request_id,
                original_request_status,
            )
        except Exception:
            pass

        try:
            update_book(
                book_id,
                original_book_values,
            )
        except Exception:
            pass

        if reservation_id and original_reservation_values is not None:
            try:
                update_reservation(
                    reservation_id,
                    original_reservation_values,
                )
            except Exception:
                pass

        return False


def get_borrow_approval_error(request_id: str):

    request = find_request(request_id)

    if request is None:
        return "Borrow request not found."

    if request["status"] != "Pending":
        return "This borrow request has already been processed."

    if has_outstanding_penalty(request["student_id"]):
        return "Student has outstanding unpaid penalties."

    book = find_book(request["book_id"])

    if book is None:
        return "Book record not found."

    if book["available_copies"] <= 0:
        return "Book is currently unavailable."

    if has_active_borrow_transaction(
        request["student_id"],
        request["book_id"],
    ):
        return "Student already has an active borrowing transaction " "for this book."

    return None


def request_book_return(transaction_id: str) -> bool:
    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    update_borrow_transaction(transaction_id, {"status": "Return Pending"})

    return True


def confirm_book_return(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Return Pending":
        return False

    update_borrow_transaction(
        transaction_id,
        {
            "status": "Returned",
            "return_date": date.today().isoformat(),
        },
    )

    book = find_book(transaction["book_id"])

    if book:
        current_available = int(book.get("available_copies", 0) or 0)
        total_copies = int(book.get("total_copies", 0) or 0)
        updated_available = current_available + 1
        if total_copies > 0:
            updated_available = min(updated_available, total_copies)

        update_book(
            transaction["book_id"],
            {
                "available_copies": updated_available,
                "status": ("Available" if updated_available > 0 else "Unavailable"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )

    return True


def request_book_renewal(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    if transaction["renewal_status"] == "Pending":
        return False

    if has_active_reservation(transaction["book_id"]):
        return False

    update_borrow_transaction(transaction_id, {"renewal_status": "Pending"})

    return True


def approve_renewal_request(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction.get("renewal_status") != "Pending":
        return False

    current_due_date = date.fromisoformat(transaction["due_date"])

    new_due_date = current_due_date + timedelta(days=14)

    book_title = get_book_title(transaction["book_id"])

    update_borrow_transaction(
        transaction_id,
        {
            "due_date": new_due_date.isoformat(),
            "renewal_status": "Approved",
            "show_renewal_message": True,
            "renewal_message": (
                f'Your renewal request for "{book_title}" '
                f"has been approved. "
                f"New due date: {new_due_date.isoformat()}."
            ),
        },
    )

    return True


def clear_renewal_alert(student_id: str) -> None:

    for transaction in get_borrow_transactions():

        if transaction["student_id"] == student_id:

            update_borrow_transaction(
                transaction["id"], {"show_renewal_message": False}
            )


def reject_renewal_request(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction.get("renewal_status") != "Pending":
        return False

    book_title = get_book_title(transaction["book_id"])

    update_borrow_transaction(
        transaction_id,
        {
            "renewal_status": "Rejected",
            "show_renewal_message": True,
            "renewal_message": (
                f'Your renewal request for "{book_title}" '
                f"has been rejected. "
                f"Please return the book before the due date."
            ),
        },
    )

    return True


def cancel_renewal_request(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction.get("renewal_status") != "Pending":
        return False

    book_title = get_book_title(transaction["book_id"])

    update_borrow_transaction(
        transaction_id,
        {
            "renewal_status": "Cancelled",
            "show_renewal_message": True,
            "renewal_message": (
                f'Your renewal request for "{book_title}" ' f"has been cancelled."
            ),
        },
    )

    return True


def manually_extend_due_date(
    transaction_id: str,
    new_due_date: str,
) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    book_title = get_book_title(transaction["book_id"])

    old_due_date = date.fromisoformat(transaction["due_date"])

    updated_due_date = date.fromisoformat(new_due_date)

    if updated_due_date <= old_due_date:
        return False

    extension_days = (updated_due_date - old_due_date).days

    update_borrow_transaction(
        transaction_id,
        {
            "due_date": updated_due_date.isoformat(),
            "renewal_status": "Manual Extension",
            "show_renewal_message": True,
            "renewal_message": (
                f'Your book "{book_title}" '
                f"has been extended by the librarian "
                f"for {extension_days} days. "
                f"New due date: "
                f"{updated_due_date.isoformat()}."
            ),
        },
    )

    return True


def close_borrow_transaction(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] not in [
        "Returned",
        "Exception Completed",  # Ong Wen Kang. If after any penalty is paid and your status is differ from mine. Can change this status. Also the borrowing/librarian.html as well.
    ]:  # Either way, so transaction could close.
        return False

    update_borrow_transaction(transaction_id, {"status": "Closed"})

    return True
