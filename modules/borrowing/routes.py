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


@borrowing_bp.post("/approve-renewal/<int:transaction_id>")
def approve_renewal(transaction_id: int):

    result = approve_renewal_request(transaction_id)

    if result:
        flash("Renewal request approved successfully.", "success")
    else:
        flash("Unable to approve renewal request.", "error")

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/clear-renewal-alert")
def clear_alert():

    clear_renewal_alert("Alice")

    return "", 204


@borrowing_bp.post("/reject-renewal/<int:transaction_id>")
def reject_renewal(transaction_id: int):

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


@borrowing_bp.post("/cancel-renewal/<int:transaction_id>")
def cancel_renewal(transaction_id: int):

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


@borrowing_bp.post("/manual-extend/<int:transaction_id>")
def manual_extend(transaction_id: int):

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


@borrowing_bp.post("/close-transaction/<int:transaction_id>")
def close_transaction(transaction_id: int):

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
