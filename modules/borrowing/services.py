from modules.borrowing.repository import (
    add_borrow_transaction,
    find_request,
    find_borrow_transaction,
    get_borrow_transactions,
    get_pending_requests,
    find_book,
    has_active_reservation,
)

from datetime import date, timedelta


# Route for Librarians
def get_all_pending_requests():
    return get_pending_requests()


def get_all_borrow_transactions():
    return get_borrow_transactions()


# Route for Students
def get_student_borrowed_books(student: str):
    return [
        transaction
        for transaction in get_borrow_transactions()
        if transaction["student"] == student
    ]


def approve_borrow_request(request_id: int) -> bool:
    request = find_request(request_id)

    if request is None:
        return False

    if request["status"] != "Pending":
        return False

    request["status"] = "Approved"

    borrow_date = date.today()
    due_date = borrow_date + timedelta(days=14)

    transaction = {
        "id": len(get_borrow_transactions()) + 1,
        "request_id": request["id"],
        "student": request["student"],
        "book": request["book"],
        "borrow_date": borrow_date.isoformat(),
        "due_date": due_date.isoformat(),
        "return_date": None,
        "status": "Borrowed",
        "renewal_status": "None",
        "show_renewal_alert": False,
        "show_renewal_message": False,
        "renewal_message": "",
    }

    add_borrow_transaction(transaction)

    return True


def request_book_return(transaction_id: int) -> bool:
    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    transaction["status"] = "Return Pending"

    return True


def confirm_book_return(transaction_id: int) -> bool:
    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Return Pending":
        return False

    transaction["status"] = "Returned"
    transaction["return_date"] = date.today().isoformat()

    book = find_book(transaction["book"])

    if book:
        book["available"] += 1

    return True


def request_book_renewal(transaction_id: int) -> bool:
    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    if transaction["renewal_status"] == "Pending":
        return False

    if has_active_reservation(transaction["book"]):
        return False

    transaction["renewal_status"] = "Pending"

    return True


def approve_renewal_request(transaction_id: int) -> bool:
    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["renewal_status"] != "Pending":
        return False

    current_due_date = date.fromisoformat(transaction["due_date"])

    new_due_date = current_due_date + timedelta(days=14)

    transaction["due_date"] = new_due_date.isoformat()

    transaction["renewal_status"] = "Approved"

    transaction["show_renewal_message"] = True

    transaction["renewal_message"] = (
        f"Your renewal request for "
        f"{transaction['book']} has been approved. "
        f"New due date: {transaction['due_date']}."
    )

    return True


def clear_renewal_alert(student: str) -> None:
    for transaction in get_borrow_transactions():
        if transaction["student"] == student:
            transaction["show_renewal_message"] = False


def reject_renewal_request(transaction_id: int) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["renewal_status"] != "Pending":
        return False

    transaction["renewal_status"] = "Rejected"

    transaction["show_renewal_message"] = True

    transaction["renewal_message"] = (
        f"Your renewal request for "
        f"{transaction['book']} has been rejected. "
        f"Please return the book before the due date."
    )

    return True


def cancel_renewal_request(transaction_id: int) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["renewal_status"] != "Pending":
        return False

    transaction["renewal_status"] = "Cancelled"

    transaction["show_renewal_message"] = True

    transaction["renewal_message"] = (
        f"Your renewal request for " f"{transaction['book']} has been cancelled."
    )

    return True


def manually_extend_due_date(transaction_id: int, new_due_date: str) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Borrowed":
        return False

    old_due_date = date.fromisoformat(transaction["due_date"])

    updated_due_date = date.fromisoformat(new_due_date)

    if updated_due_date <= old_due_date:
        return False

    extension_days = (updated_due_date - old_due_date).days

    transaction["due_date"] = updated_due_date.isoformat()

    transaction["renewal_status"] = "Manual Extension"

    transaction["show_renewal_message"] = True

    transaction["renewal_message"] = (
        f"Your book {transaction['book']} "
        f"has been extended by the librarian "
        f"for {extension_days} days. "
        f"New due date: {transaction['due_date']}."
    )

    return True


def close_borrow_transaction(transaction_id: int) -> bool:

    transaction = find_borrow_transaction(transaction_id)

    if transaction is None:
        return False

    if transaction["status"] != "Returned":
        return False

    transaction["status"] = "Closed"

    return True
