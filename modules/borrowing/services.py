from modules.borrowing.repository import (
    add_borrow_transaction,
    find_request,
    find_borrow_transaction,
    get_borrow_transactions,
    get_pending_requests,
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
