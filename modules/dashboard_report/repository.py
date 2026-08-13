"""Firestore read operations for the dashboard module."""

from config.firebase_config import (
    COLLECTION_BOOKS,
    COLLECTION_BORROW_REQUESTS,
    COLLECTION_BORROW_TRANSACTIONS,
    COLLECTION_PENALTIES,
    COLLECTION_RESERVATIONS,
    COLLECTION_USERS,
    db,
)


def _student_records(collection_name, student_id):
    """Return records owned by one student from a Firestore collection."""
    documents = (
        db.collection(collection_name)
        .where("student_id", "==", student_id)
        .stream()
    )

    records = []

    for document in documents:
        record = document.to_dict() or {}
        record.setdefault("document_id", document.id)
        records.append(record)

    return records


def get_student_borrow_requests(student_id):
    return _student_records(COLLECTION_BORROW_REQUESTS, student_id)


def get_student_borrow_transactions(student_id):
    return _student_records(COLLECTION_BORROW_TRANSACTIONS, student_id)


def get_student_reservations(student_id):
    return _student_records(COLLECTION_RESERVATIONS, student_id)


def get_student_penalties(student_id):
    return _student_records(COLLECTION_PENALTIES, student_id)


def get_book_by_id(book_id):
    """Return one book record for dashboard display, or None when missing."""
    if not book_id or not str(book_id).strip():
        return None

    document = db.collection(COLLECTION_BOOKS).document(str(book_id).strip()).get()

    if not getattr(document, "exists", False):
        return None

    book = document.to_dict() or {}
    book.setdefault("book_id", document.id)
    return book



def _all_records(collection_name):
    """Return every record from one dashboard data source."""
    records = []

    for document in db.collection(collection_name).stream():
        record = document.to_dict() or {}
        record.setdefault("document_id", document.id)
        records.append(record)

    return records


def get_all_users():
    return _all_records(COLLECTION_USERS)


def get_all_books():
    return _all_records(COLLECTION_BOOKS)


def get_all_borrow_requests():
    return _all_records(COLLECTION_BORROW_REQUESTS)


def get_all_borrow_transactions():
    return _all_records(COLLECTION_BORROW_TRANSACTIONS)


def get_all_reservations():
    return _all_records(COLLECTION_RESERVATIONS)


def get_all_penalties():
    return _all_records(COLLECTION_PENALTIES)
