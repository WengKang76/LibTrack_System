from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date, timedelta

try:
    from config.firebase_config import db, COLLECTION_BORROW_TRANSACTIONS
except ImportError:
    from config.firebase_config import db
    COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"


penalty_bp = Blueprint(
    "penalty_transaction",
    __name__,
    url_prefix="/penalty",
    template_folder="."
)


# =========================================================
# DEMO DATA FOR UI PREVIEW
# =========================================================

DEMO_UI_MODE = True

DEMO_BORROW_TRANSACTIONS = {
    "T001": {
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "borrow_date": "2026-07-01",
        "due_date": (date.today() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "status": "Borrowed"
    },
    "T002": {
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "borrow_date": "2026-07-05",
        "due_date": (date.today() + timedelta(days=3)).strftime("%Y-%m-%d"),
        "status": "Borrowed"
    },
    "T003": {
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "borrow_date": "2026-07-01",
        "due_date": (date.today() - timedelta(days=2)).strftime("%Y-%m-%d"),
        "status": "Returned"
    }
}


DEMO_PENALTIES = {
    "P001": {
        "penalty_id": "P001",
        "student_id": "S001",
        "transaction_id": "T001",
        "book_title": "Python Programming",
        "overdue_days": 5,
        "penalty_amount": 5.00,
        "status": "Outstanding"
    },
    "P002": {
        "penalty_id": "P002",
        "student_id": "S002",
        "transaction_id": "T002",
        "book_title": "Database System",
        "overdue_days": 3,
        "penalty_amount": 3.00,
        "status": "Paid"
    },
    "P003": {
        "penalty_id": "P003",
        "student_id": "S003",
        "transaction_id": "T003",
        "book_title": "Software Engineering",
        "overdue_days": 2,
        "penalty_amount": 2.00,
        "status": "Waived"
    }
}


# =========================================================
# HELPER FUNCTIONS
# =========================================================

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


def get_overdue_books():
    today = date.today()
    overdue_books = []

    try:
        docs = db.collection(COLLECTION_BORROW_TRANSACTIONS).stream()

        for doc in docs:
            transaction = doc.to_dict()
            transaction["transaction_id"] = doc.id

            due_date = convert_to_date(transaction.get("due_date"))
            status = str(transaction.get("status", "")).lower()

            if due_date and due_date < today and status != "returned":
                overdue_books.append(transaction)

    except Exception:
        pass

    # Demo fallback data for UI preview
    if DEMO_UI_MODE and len(overdue_books) == 0:
        for transaction_id, transaction in DEMO_BORROW_TRANSACTIONS.items():
            demo_transaction = transaction.copy()
            demo_transaction["transaction_id"] = transaction_id

            due_date = convert_to_date(demo_transaction.get("due_date"))
            status = str(demo_transaction.get("status", "")).lower()

            if due_date and due_date < today and status != "returned":
                overdue_books.append(demo_transaction)

    return overdue_books


PENALTY_RATE_PER_DAY = 1.00


def calculate_penalty_amount(due_date):
    due_date = convert_to_date(due_date)
    today = date.today()

    if due_date is None:
        return {
            "overdue_days": 0,
            "penalty_amount": 0.00
        }

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

    try:
        penalty_docs = db.collection("penalties").stream()

        for doc in penalty_docs:
            penalty = doc.to_dict()
            penalty["penalty_id"] = doc.id

            status = str(penalty.get("status", "")).lower()

            if status in ["outstanding", "unpaid", "pending"]:
                if student_id is None or penalty.get("student_id") == student_id:
                    outstanding_penalties.append(penalty)

    except Exception:
        pass

    # Demo fallback data for UI preview
    if DEMO_UI_MODE and len(outstanding_penalties) == 0:
        for penalty_id, penalty in DEMO_PENALTIES.items():
            demo_penalty = penalty.copy()
            demo_penalty["penalty_id"] = penalty_id

            status = str(demo_penalty.get("status", "")).lower()

            if status in ["outstanding", "unpaid", "pending"]:
                if student_id is None or demo_penalty.get("student_id") == student_id:
                    outstanding_penalties.append(demo_penalty)

    return outstanding_penalties


def get_penalty_by_id(penalty_id):
    try:
        penalty_doc = db.collection("penalties").document(penalty_id).get()

        if penalty_doc.exists:
            penalty = penalty_doc.to_dict()
            penalty["penalty_id"] = penalty_doc.id
            return penalty

    except Exception:
        pass

    # Demo fallback data for UI preview
    if DEMO_UI_MODE:
        penalty = DEMO_PENALTIES.get(penalty_id)

        if penalty:
            return penalty.copy()

    return None


def pay_penalty_with_credit_card(penalty_id, card_number):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    card_number = card_number.replace(" ", "").replace("-", "")

    if not card_number.isdigit() or len(card_number) < 12:
        return False, "Invalid credit card number."

    payment_data = {
        "status": "Paid",
        "payment_method": "Credit Card",
        "payment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "card_last_four": card_number[-4:],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(payment_data)
    except Exception:
        pass

    # Update hardcoded demo data also
    if penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(payment_data)

    return True, "Penalty paid successfully using credit card."

def pay_penalty_with_cash(penalty_id, cash_amount):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    try:
        cash_amount = float(cash_amount)
    except ValueError:
        return False, "Invalid cash amount."

    penalty_amount = float(penalty.get("penalty_amount", 0))

    if cash_amount < penalty_amount:
        return False, "Cash amount is less than the penalty amount."

    change_amount = cash_amount - penalty_amount

    payment_data = {
        "status": "Paid",
        "payment_method": "Cash",
        "paid_by": "Student",
        "cash_amount_received": cash_amount,
        "change_amount": change_amount,
        "payment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(payment_data)
    except Exception:
        pass

    if penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(payment_data)

    return True, "Cash penalty payment completed successfully."
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return False, "Penalty record not found."

    status = str(penalty.get("status", "")).lower()

    if status not in ["outstanding", "unpaid", "pending"]:
        return False, "Only outstanding penalties can be paid."

    try:
        cash_amount = float(cash_amount)
    except ValueError:
        return False, "Invalid cash amount."

    penalty_amount = float(penalty.get("penalty_amount", 0))

    if cash_amount < penalty_amount:
        return False, "Cash amount is less than the penalty amount."

    change_amount = cash_amount - penalty_amount

    payment_data = {
        "status": "Paid",
        "payment_method": "Cash",
        "cash_amount_received": cash_amount,
        "change_amount": change_amount,
        "received_by": received_by,
        "payment_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        db.collection("penalties").document(penalty_id).update(payment_data)
    except Exception:
        pass

    # Update hardcoded demo data also
    if penalty_id in DEMO_PENALTIES:
        DEMO_PENALTIES[penalty_id].update(payment_data)

    return True, "Cash penalty payment recorded successfully."


# =========================================================
# ROUTES
# =========================================================

@penalty_bp.route("/overdue")
@penalty_bp.route("/librarian/overdue")
def identify_overdue_books():
    overdue_books = get_overdue_books()

    return render_template(
        "librarian/overdue_book.html",
        overdue_books=overdue_books
    )


@penalty_bp.route("/penalties")
@penalty_bp.route("/outstanding")
@penalty_bp.route("/librarian/penalties")
def view_outstanding_penalties():
    student_id = request.args.get("student_id")

    if student_id:
        student_id = student_id.strip()

    outstanding_penalties = get_outstanding_penalties(student_id)

    return render_template(
        "librarian/outstanding_penalties.html",
        outstanding_penalties=outstanding_penalties,
        student_id=student_id
    )


@penalty_bp.route("/pay-credit-card/<penalty_id>", methods=["GET", "POST"])
@penalty_bp.route("/student/pay-credit-card/<penalty_id>", methods=["GET", "POST"])
def student_pay_credit_card(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        card_number = request.form.get("card_number", "").strip()

        success, message = pay_penalty_with_credit_card(
            penalty_id,
            card_number
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_credit_card.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "student/pay_credit_card.html",
        penalty=penalty
    )

@penalty_bp.route("/student/pay-cash/<penalty_id>", methods=["GET", "POST"])
def student_pay_cash(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()

        success, message = pay_penalty_with_cash(
            penalty_id,
            cash_amount
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_cash.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "student/pay_cash.html",
        penalty=penalty
    )

def student_pay_cash(penalty_id):
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()

        success, message = pay_penalty_with_cash(
            penalty_id,
            cash_amount
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "student/pay_cash.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "student/pay_cash.html",
        penalty=penalty
    )
    penalty = get_penalty_by_id(penalty_id)

    if penalty is None:
        return "Penalty record not found", 404

    if request.method == "POST":
        cash_amount = request.form.get("cash_amount", "").strip()
        received_by = request.form.get("received_by", "Librarian").strip()

        success, message = pay_penalty_with_cash(
            penalty_id,
            cash_amount,
            received_by
        )

        if success:
            flash(message, "success")
            return redirect(url_for("penalty_transaction.view_outstanding_penalties"))

        return render_template(
            "librarian/pay_cash.html",
            penalty=penalty,
            error=message
        ), 400

    return render_template(
        "librarian/pay_cash.html",
        penalty=penalty
    )