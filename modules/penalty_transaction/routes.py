from flask import Blueprint, render_template
from datetime import datetime, date

from config.firebase_config import db, COLLECTION_BORROW_TRANSACTIONS


penalty_bp = Blueprint(
    "penalty_transaction",
    __name__,
    url_prefix="/penalty",
    template_folder="."
)


@penalty_bp.route("/overdue")
def identify_overdue_books():
    overdue_books = get_overdue_books()

    return render_template(
        "overdue_book.html",
        overdue_books=overdue_books
    )


def get_overdue_books():
    today = date.today()
    overdue_books = []

    docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

    for doc in docs:
        transaction = doc.to_dict()
        transaction["transaction_id"] = doc.id

        status = str(transaction.get("status", "")).lower()
        due_date = transaction.get("due_date")

        converted_due_date = convert_to_date(due_date)

        if converted_due_date and converted_due_date < today and status != "returned":
            overdue_books.append(transaction)

    return overdue_books


def convert_to_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    return None