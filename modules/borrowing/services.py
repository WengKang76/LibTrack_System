from modules.borrowing.repository import (
    add_borrow_transaction,
    find_request,
    find_borrow_transaction,
    get_borrow_transactions,
    get_pending_requests,
    find_book,
    has_active_reservation,
    update_book,
    update_borrow_transaction,
    update_request_status,
)

from datetime import date, timedelta


def get_book_title(book_id: str) -> str:

    book = find_book(book_id)

    if book:
        return book.get("title", "Unknown Book")

    return "Unknown Book"

# Route for Librarians
def get_all_pending_requests():
    return get_pending_requests()


def get_all_borrow_transactions():
    return get_borrow_transactions()


# Route for Students
def get_student_borrowed_books(student_id: str):

    return [
        transaction
        for transaction in get_borrow_transactions()
        if transaction["student_id"] == student_id
        and transaction["status"]
        in [
            "Borrowed",
            "Return Pending",
        ]
    ]


def approve_borrow_request(request_id: str):

    request = find_request(request_id)

    if request is None:
        return False

    if request["status"] != "Pending":
        return False

    update_request_status(request_id, "Approved")

    borrow_date = date.today()
    due_date = borrow_date + timedelta(days=14)

    transaction = {
        "request_id": request_id,
        "book_id": request["book_id"],
        "student_id": request["student_id"],
        "borrow_date": borrow_date.isoformat(),
        "due_date": due_date.isoformat(),
        "return_date": None,
        "status": "Borrowed",
        "renewal_status": "None",
        "show_renewal_message": False,
        "renewal_message": "",
    }

    transaction_id = add_borrow_transaction(transaction)

    return transaction_id


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

        current_available = book.get("available_copies", 0)

        update_book(transaction["book_id"], {"available_copies": current_available + 1})

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
                f'has been approved. '
                f'New due date: {new_due_date.isoformat()}.'
            ),
        },
    )

    return True


def clear_renewal_alert(student_id: str) -> None:

    for transaction in get_borrow_transactions():

        if transaction["student_id"] == student_id:

            update_borrow_transaction(
                transaction["id"],
                {
                    "show_renewal_message": False
                }
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
                f'has been rejected. '
                f'Please return the book before the due date.'
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
                f'Your renewal request for "{book_title}" '
                f'has been cancelled.'
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
                f'has been extended by the librarian '
                f'for {extension_days} days. '
                f'New due date: '
                f'{updated_due_date.isoformat()}.'
            ),
        },
    )

    return True


def close_borrow_transaction(transaction_id: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Returned":
        return False

    update_borrow_transaction(transaction_id, {"status": "Closed"})

    return True
