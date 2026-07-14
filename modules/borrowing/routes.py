from flask import Blueprint, flash, redirect, render_template, url_for

from modules.borrowing.services import (
    approve_borrow_request,
    get_all_borrow_transactions,
    get_all_pending_requests,
    get_student_borrowed_books,
    request_book_return,
    confirm_book_return,
    request_book_renewal,
)

borrowing_bp = Blueprint(
    "borrowing",
    __name__,
    url_prefix="/borrowing",
)


@borrowing_bp.route("/")
def borrowing_home():
    requests = get_all_pending_requests()
    transactions = get_all_borrow_transactions()

    return render_template(
        "borrowing/index.html",
        requests=requests,
        transactions=transactions,
    )


@borrowing_bp.route("/approve/<int:request_id>", methods=["POST"])
def approve_request(request_id: int):
    success = approve_borrow_request(request_id)

    if not success:
        return "Invalid borrow request", 400

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/return/<int:transaction_id>")
def return_book(transaction_id: int):
    request_book_return(transaction_id)
    return redirect(url_for("borrowing.student_books"))


@borrowing_bp.route("/student")
def student_books():
    books = get_student_borrowed_books("Alice")

    return render_template(
        "borrowing/student_books.html",
        books=books,
    )


@borrowing_bp.post("/confirm-return/<int:transaction_id>")
def confirm_return(transaction_id: int):
    confirm_book_return(transaction_id)

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/renew-book/<int:transaction_id>")
def renew_book(transaction_id: int):

    result = request_book_renewal(transaction_id)

    if result:
        flash(
            "Renewal request submitted successfully. Waiting for librarian approval.",
            "success",
        )
    else:
        flash(
            "Renewal unavailable. Another student has reserved this book. Please return the book on time.",
            "error",
        )

    return redirect(url_for("borrowing.student_books"))
