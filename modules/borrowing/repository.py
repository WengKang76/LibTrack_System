from typing import TypedDict


class BorrowRequest(TypedDict):
    id: int
    student: str
    book: str
    status: str


class BorrowTransaction(TypedDict):
    id: int
    request_id: int
    student: str
    book: str
    borrow_date: str
    due_date: str
    return_date: str | None
    status: str


borrow_requests: list[BorrowRequest] = [
    {
        "id": 1,
        "student": "Alice",
        "book": "Database System Concepts",
        "status": "Pending",
    },
    {
        "id": 2,
        "student": "John",
        "book": "Software Engineering",
        "status": "Pending",
    },
]

borrow_transactions: list[BorrowTransaction] = []

"""
Temporary book data for testing and development purposes.
Remove this when database is implemented.
"""

books = [
    {
        "title": "Database System Concepts",
        "available": 0,
    },
    {
        "title": "Software Engineering",
        "available": 0,
    },
]


def get_pending_requests() -> list[BorrowRequest]:
    return [request for request in borrow_requests if request["status"] == "Pending"]


def find_request(request_id: int) -> BorrowRequest | None:
    for request in borrow_requests:
        if request["id"] == request_id:
            return request

    return None


def find_borrow_transaction(
    transaction_id: int,
) -> BorrowTransaction | None:
    for transaction in borrow_transactions:
        if transaction["id"] == transaction_id:
            return transaction

    return None


def add_borrow_transaction(transaction: BorrowTransaction) -> None:
    borrow_transactions.append(transaction)


def get_borrow_transactions() -> list[BorrowTransaction]:
    return borrow_transactions


def find_book(book_title: str):
    for book in books:
        if book["title"] == book_title:
            return book

    return None
