import time

from flask import Blueprint, flash, redirect, render_template, request, url_for

from modules.authentication.decorators import librarian_required, student_required

from modules.borrowing.services import (
    paginate_records,
    approve_borrow_request,
    get_borrow_approval_error,
    cancel_renewal_request,
    clear_renewal_alert,
    close_borrow_transaction,
    get_all_borrow_transactions,
    get_filtered_pending_requests,
    get_filtered_borrow_transactions,
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
@librarian_required
def borrowing_home():

    keyword = request.args.get(
        "request_keyword",
        "",
    ).strip()

    status = request.args.get(
        "request_status",
        "All",
    )

    sort_by = request.args.get(
        "request_sort",
        "id",
    )

    sort_order = request.args.get(
        "request_order",
        "asc",
    )

    request_page = request.args.get(
        "request_page",
        1,
    )

    request_per_page = request.args.get(
        "request_per_page",
        10,
    )

    requests_results = get_filtered_pending_requests(
        keyword=keyword,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    request_pagination = paginate_records(
        requests_results,
        request_page,
        request_per_page,
    )

    requests = request_pagination["records"]

    transaction_keyword = request.args.get(
        "transaction_keyword",
        "",
    ).strip()

    transaction_page = request.args.get(
        "transaction_page",
        1,
    )

    transaction_per_page = request.args.get(
        "transaction_per_page",
        10,
    )

    transaction_status = request.args.get(
        "transaction_status",
        "All",
    )

    transaction_sort = request.args.get(
        "transaction_sort",
        "id",
    )

    transaction_order = request.args.get(
        "transaction_order",
        "asc",
    )

    start = time.perf_counter()

    requests_results = get_filtered_pending_requests(
        keyword=keyword,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    print(f"Pending requests: " f"{time.perf_counter() - start:.3f} seconds")

    start = time.perf_counter()

    transaction_results = get_filtered_borrow_transactions(
        keyword=transaction_keyword,
        status=transaction_status,
        sort_by=transaction_sort,
        sort_order=transaction_order,
    )

    print(f"Borrow transactions: " f"{time.perf_counter() - start:.3f} seconds")

    transaction_pagination = paginate_records(
        transaction_results,
        transaction_page,
        transaction_per_page,
    )

    transactions = transaction_pagination["records"]

    return render_template(
        "borrowing/librarian.html",
        requests=requests,
        transactions=transactions,
        request_keyword=keyword,
        request_status=status,
        request_sort=sort_by,
        request_order=sort_order,
        transaction_keyword=transaction_keyword,
        transaction_status=transaction_status,
        transaction_sort=transaction_sort,
        transaction_order=transaction_order,
        request_pagination=request_pagination,
        transaction_pagination=transaction_pagination,
    )


@borrowing_bp.route("/transactions/table")
@librarian_required
def transaction_table():
    transaction_keyword = request.args.get(
        "transaction_keyword",
        "",
    ).strip()

    transaction_status = request.args.get(
        "transaction_status",
        "All",
    )

    transaction_sort = request.args.get(
        "transaction_sort",
        "id",
    )

    transaction_order = request.args.get(
        "transaction_order",
        "asc",
    )

    transaction_page = request.args.get(
        "transaction_page",
        1,
    )

    transaction_per_page = request.args.get(
        "transaction_per_page",
        10,
    )

    transaction_results = get_filtered_borrow_transactions(
        keyword=transaction_keyword,
        status=transaction_status,
        sort_by=transaction_sort,
        sort_order=transaction_order,
    )

    transaction_pagination = paginate_records(
        transaction_results,
        transaction_page,
        transaction_per_page,
    )

    transactions = transaction_pagination["records"]

    return render_template(
        "borrowing/_transaction_table.html",
        transactions=transactions,
        transaction_keyword=transaction_keyword,
        transaction_status=transaction_status,
        transaction_sort=transaction_sort,
        transaction_order=transaction_order,
        transaction_pagination=transaction_pagination,
    )


@borrowing_bp.route("/approve/<request_id>", methods=["POST"])
@librarian_required
def approve_request(request_id: str):

    error = get_borrow_approval_error(request_id)

    if error:
        flash(error, "error")
        return redirect(url_for("borrowing.borrowing_home"))

    approve_borrow_request(request_id)

    flash("Borrow request approved successfully.", "success")

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/return/<transaction_id>")
@student_required
def return_book(transaction_id: str):
    request_book_return(transaction_id)
    return redirect(url_for("catalogue_reservation.view_currently_borrowed_books"))


# Student Page Routes with test user "USR001" Alice,
# replace "USR001" with session["user_id"] after implementing login system
@borrowing_bp.route("/student")
@librarian_required
def student_books():

    books = get_student_borrowed_books("USR001")

    return render_template(
        "borrowing/student_books.html",
        books=books,
    )


@borrowing_bp.post("/confirm-return/<transaction_id>")
@librarian_required
def confirm_return(transaction_id: str):
    confirm_book_return(transaction_id)

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/renew-book/<transaction_id>")
@student_required
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

    return redirect(url_for("catalogue_reservation.view_currently_borrowed_books"))


@borrowing_bp.post("/approve-renewal/<transaction_id>")
@librarian_required
def approve_renewal(transaction_id: str):

    result = approve_renewal_request(transaction_id)

    if result:
        flash("Renewal request approved successfully.", "success")
    else:
        flash("Unable to approve renewal request.", "error")

    return redirect(url_for("borrowing.borrowing_home"))


@borrowing_bp.post("/clear-renewal-alert")
@librarian_required
def clear_alert():

    student_id = "USR001"  # replace with logged-in user later

    clear_renewal_alert(student_id)

    return ""


@borrowing_bp.post("/reject-renewal/<transaction_id>")
@librarian_required
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
@student_required
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

    return redirect(url_for("catalogue_reservation.view_currently_borrowed_books"))


@borrowing_bp.post("/manual-extend/<transaction_id>")
@librarian_required
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
@librarian_required
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
