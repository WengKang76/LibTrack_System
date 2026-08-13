from typing import TypedDict

from config.firebase_config import (
    db,
    COLLECTION_BOOKS,
    COLLECTION_BORROW_REQUESTS,
    COLLECTION_BORROW_TRANSACTIONS,
    COLLECTION_USERS,
    COLLECTION_RESERVATIONS,
    COLLECTION_PENALTIES,
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


def delete_borrow_transaction(transaction_id: str):
    db = get_db()
    db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).delete()


def get_borrow_transactions():
    db = get_db()
    docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

    transactions = []

    book_cache = {}
    user_cache = {}

    for doc in docs:
        data = doc.to_dict()

        book_id = data["book_id"]
        student_id = data["student_id"]

        # Get book information from cache or Firestore
        if book_id not in book_cache:
            book_doc = db.collection(COLLECTION_BOOKS).document(book_id).get()

            book_cache[book_id] = book_doc.to_dict() if book_doc.exists else {}

        # Get student information from cache or Firestore
        if student_id not in user_cache:
            user_doc = db.collection(COLLECTION_USERS).document(student_id).get()

            user_cache[student_id] = user_doc.to_dict() if user_doc.exists else {}

        book = book_cache[book_id]
        user = user_cache[student_id]

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


def find_reservation(reservation_id: str):
    db = get_db()
    doc = db.collection(COLLECTION_RESERVATIONS).document(reservation_id).get()

    if not doc.exists:
        return None

    reservation = doc.to_dict() or {}
    reservation["id"] = doc.id

    return reservation


def update_reservation(
    reservation_id: str,
    updates: dict,
):
    db = get_db()
    (db.collection(COLLECTION_RESERVATIONS).document(reservation_id).update(updates))


# ==========================
# Penalties
# ==========================


def has_outstanding_penalty(student_id: str) -> bool:
    db = get_db()

    docs = (
        db.collection(COLLECTION_PENALTIES)
        .where("student_id", "==", student_id)
        .where("status", "==", "Outstanding")
        .stream()
    )

    return any(True for _ in docs)


# ==========================
# Active Borrow Transactions
# ==========================


def has_active_borrow_transaction(
    student_id: str,
    book_id: str,
) -> bool:
    db = get_db()

    docs = (
        db.collection(COLLECTION_BORROW_TRANSACTIONS)
        .where("student_id", "==", student_id)
        .where("book_id", "==", book_id)
        .stream()
    )

    active_statuses = {
        "Borrowed",
        "Return Pending",
    }

    for doc in docs:
        transaction = doc.to_dict() or {}

        if transaction.get("status") in active_statuses:
            return True

    return False
