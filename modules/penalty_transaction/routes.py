from flask import Blueprint, render_template, request
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

PENALTY_RATE_PER_DAY = 1.00


def calculate_penalty_amount(due_date):
    today = date.today()

    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

    if due_date >= today:
        return {
            "overdue_days": 0,
            "penalty_amount": 0.00
        }

    overdue_days = (today - due_date).days
    penalty_amount = overdue_days * PENALTY_RATE_PER_DAY

    return {
        "overdue_days": overdue_days,
        "penalty_amount": penalty_amount
    }
    today = date.today()

    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()

    if due_date >= today:
        return {
            "overdue_days": 0,
            "penalty_amount": 0.00
        }

    overdue_days = (today - due_date).days
    penalty_amount = overdue_days * PENALTY_RATE_PER_DAY

    return {
        "overdue_days": overdue_days,
        "penalty_amount": penalty_amount
    }


def get_outstanding_penalties(student_id=None):
    outstanding_penalties = []

    penalty_docs = db.collection("penalties").stream()

    for doc in penalty_docs:
        penalty = doc.to_dict()
        penalty["penalty_id"] = doc.id

        status = str(penalty.get("status", "")).lower()

        if status in ["outstanding", "unpaid", "pending"]:
            if student_id is None or penalty.get("student_id") == student_id:
                outstanding_penalties.append(penalty)

    return outstanding_penalties


@penalty_bp.route("/penalties")
@penalty_bp.route("/outstanding")
def view_outstanding_penalties():
    student_id = request.args.get("student_id")

    if student_id:
        student_id = student_id.strip()

    outstanding_penalties = get_outstanding_penalties(student_id)

    return render_template(
        "outstanding_penalties.html",
        outstanding_penalties=outstanding_penalties,
        student_id=student_id
    )


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