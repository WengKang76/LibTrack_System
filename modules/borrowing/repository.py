from typing import TypedDict

from config.firebase_config import (
    db,
    COLLECTION_BOOKS,
    COLLECTION_BORROW_REQUESTS,
    COLLECTION_BORROW_TRANSACTIONS,
    COLLECTION_USERS,
    COLLECTION_RESERVATIONS,
)


def get_db():

    return db


class BorrowRequest(TypedDict):
    id: str
    book_id: str
    student_id: str
    borrowing_period: int
    request_date: str
    status: str


class BorrowTransaction(TypedDict):
    id: str
    request_id: str
    student_id: str
    book_id: str
    borrow_date: str
    due_date: str
    return_date: str | None
    status: str
    renewal_status: str
    show_renewal_message: bool
    renewal_message: str


# ==========================
# Borrow Request
# ==========================


def get_pending_requests():
    db = get_db()

    docs = (
        db.collection(COLLECTION_BORROW_REQUESTS)
        .where("status", "==", "Pending")
        .stream()
    )

    requests = []

    for doc in docs:

        data = doc.to_dict()

        book_doc = db.collection(COLLECTION_BOOKS).document(data["book_id"]).get()

        user_doc = db.collection(COLLECTION_USERS).document(data["student_id"]).get()

        book = book_doc.to_dict() if book_doc.exists else {}
        user = user_doc.to_dict() if user_doc.exists else {}

        requests.append(
            {
                "id": doc.id,
                "student": user.get("full_name", "Unknown"),
                "book": book.get("title", "Unknown"),
                "status": data["status"],
            }
        )

    return requests


def find_request(request_id: str):

    db = get_db()

    doc = db.collection(COLLECTION_BORROW_REQUESTS).document(request_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()

    data["id"] = doc.id

    return data


def update_request_status(
    request_id: str,
    status: str,
):
    db = get_db()
    db.collection(COLLECTION_BORROW_REQUESTS).document(request_id).update(
        {"status": status}
    )


# ==========================
# Borrow Transactions
# ==========================


def add_borrow_transaction(transaction):

    db = get_db()
    ref = db.collection(COLLECTION_BORROW_TRANSACTIONS).add(transaction)

    return ref[1].id


def get_borrow_transactions():

    db = get_db()
    docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

    transactions = []

    for doc in docs:

        data = doc.to_dict()

        book_doc = db.collection(COLLECTION_BOOKS).document(data["book_id"]).get()

        user_doc = db.collection(COLLECTION_USERS).document(data["student_id"]).get()

        book = book_doc.to_dict() if book_doc.exists else {}
        user = user_doc.to_dict() if user_doc.exists else {}

        data["id"] = doc.id
        data["book"] = book.get("title", "Unknown")
        data["student"] = user.get("full_name", "Unknown")

        transactions.append(data)

    return transactions


def find_borrow_transaction(transaction_id: str):
    db = get_db()
    doc = db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()

    data["id"] = doc.id

    return data


def update_borrow_transaction(
    transaction_id: str,
    updates: dict,
):

    db = get_db()
    db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).update(
        updates
    )


# ==========================
# Books
# ==========================


def find_book(book_id: str):
    db = get_db()
    doc = db.collection(COLLECTION_BOOKS).document(book_id).get()

    if not doc.exists:
        return None

    book = doc.to_dict()

    book["id"] = doc.id

    return book


def update_book(
    book_id: str,
    updates: dict,
):
    db = get_db()
    db.collection(COLLECTION_BOOKS).document(book_id).update(updates)


# ==========================
# Reservations
# ==========================


def has_active_reservation(book_id: str):

    db = get_db()
    docs = (
        db.collection(COLLECTION_RESERVATIONS)
        .where(
            "book_id",
            "==",
            book_id,
        )
        .where(
            "status",
            "==",
            "Pending",
        )
        .stream()
    )

    return any(True for _ in docs)
