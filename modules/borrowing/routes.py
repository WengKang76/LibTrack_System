from flask import Blueprint, flash, redirect, render_template, request, url_for

from modules.borrowing.services import (
    approve_borrow_request,
    cancel_renewal_request,
    clear_renewal_alert,
    close_borrow_transaction,
    get_all_borrow_transactions,
    get_all_pending_requests,
    get_student_borrowed_books,
    manually_extend_due_date,
    reject_renewal_request,
    request_book_return,
    confirm_book_return,
    request_book_renewal,
    approve_renewal_request,
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
        "borrowing/librarian.html",
        requests=requests,
        transactions=transactions,
    )


@borrowing_bp.route("/approve/<request_id>", methods=["POST"])
def approve_request(request_id: str):
    success = approve_borrow_request(request_id)

    if not success:
        return "Invalid borrow request", 400

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/return/<transaction_id>")
def return_book(transaction_id: str):
    request_book_return(transaction_id)
    return redirect(url_for("borrowing.student_books"))


# Student Page Routes with test user "USR001" Alice,
# replace "USR001" with session["user_id"] after implementing login system
@borrowing_bp.route("/student")
def student_books():

    books = get_student_borrowed_books("USR001")

    return render_template(
        "borrowing/student_books.html",
        books=books,
    )


@borrowing_bp.post("/confirm-return/<transaction_id>")
def confirm_return(transaction_id: str):
    confirm_book_return(transaction_id)

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/renew-book/<transaction_id>")
def renew_book(transaction_id: str):

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


@borrowing_bp.post("/approve-renewal/<transaction_id>")
def approve_renewal(transaction_id: str):

    result = approve_renewal_request(transaction_id)

    if result:
        flash("Renewal request approved successfully.", "success")
    else:
        flash("Unable to approve renewal request.", "error")

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/clear-renewal-alert")
def clear_alert():

    student_id = "USR001" # replace with logged-in user later

    clear_renewal_alert(student_id)

    return ""


@borrowing_bp.post("/reject-renewal/<transaction_id>")
def reject_renewal(transaction_id: str):

    result = reject_renewal_request(transaction_id)

    if result:
        flash(
            "Renewal request rejected.",
            "success",
        )
    else:
        flash(
            "Unable to reject renewal request.",
            "error",
        )

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/cancel-renewal/<transaction_id>")
def cancel_renewal(transaction_id: str):

    result = cancel_renewal_request(transaction_id)

    if result:
        flash(
            "Renewal request cancelled successfully.",
            "success",
        )
    else:
        flash(
            "Unable to cancel renewal request.",
            "error",
        )

    return redirect(url_for("borrowing.student_books"))


@borrowing_bp.post("/manual-extend/<transaction_id>")
def manual_extend(transaction_id: str):

    new_due_date = request.form["new_due_date"]

    result = manually_extend_due_date(
        transaction_id,
        new_due_date,
    )

    if result:
        flash(
            "Due date extended successfully.",
            "success",
        )
    else:
        flash(
            "Unable to extend due date.",
            "error",
        )

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/close-transaction/<transaction_id>")
def close_transaction(transaction_id: str):

    result = close_borrow_transaction(transaction_id)

    if result:
        flash(
            "Borrowing transaction closed successfully.",
            "success",
        )
    else:
        flash(
            "Unable to close borrowing transaction.",
            "error",
        )

    return redirect(url_for("borrowing.borrowing_home"))
