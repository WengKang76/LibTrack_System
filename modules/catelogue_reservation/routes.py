from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime

from config.firebase_config import db

catalogue_bp = Blueprint(
    "catalogue_reservation",
    __name__,
    url_prefix="/catalogue"
)

BOOKS_COLLECTION = "books"
RESERVATIONS_COLLECTION = "reservations"
BORROW_REQUESTS_COLLECTION = "borrow_requests"


# SCRUM-44: Setup module + View book catalogue
@catalogue_bp.route("/")
def view_catalogue():
    books = []

    search_keyword = request.args.get("search", "").strip().lower()

    try:
        docs = db.collection(BOOKS_COLLECTION).stream()

        for doc in docs:
            book = doc.to_dict()
            book["book_id"] = doc.id

            if search_keyword:
                title = str(book.get("title", "")).lower()
                author = str(book.get("author", "")).lower()
                category = str(book.get("category", "")).lower()

                if (
                    search_keyword in title
                    or search_keyword in author
                    or search_keyword in category
                ):
                    books.append(book)
            else:
                books.append(book)

    except Exception as error:
        flash(f"Error loading catalogue: {error}")

    return render_template(
        "catalogue_reservation/view_catalogue.html",
        books=books,
        search_keyword=search_keyword
    )


# SCRUM-684: Display all available books
@catalogue_bp.route("/available")
def view_available_books():
    books = []

    try:
        docs = db.collection(BOOKS_COLLECTION).stream()

        for doc in docs:
            book = doc.to_dict()
            book["book_id"] = doc.id

            status = str(book.get("status", "")).lower()
            available_copies = int(book.get("available_copies", 0))

            if status == "available" and available_copies > 0:
                books.append(book)

    except Exception as error:
        flash(f"Error loading available books: {error}")

    return render_template(
        "catalogue_reservation/view_catalogue.html",
        books=books,
        search_keyword=""
    )


# SCRUM-689: Reserve an unavailable book
@catalogue_bp.route("/reserve/<book_id>")
def reserve_book(book_id):
    student_id = "S001"  # temporary hardcoded user for Sprint 1

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            flash("Book not found.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        book = book_doc.to_dict()

        available_copies = int(book.get("available_copies", 0))
        status = str(book.get("status", "")).lower()

        if status == "available" and available_copies > 0:
            flash("This book is available. You do not need to reserve it.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        # Check duplicate reservation
        existing_reservations = db.collection(RESERVATIONS_COLLECTION) \
            .where("student_id", "==", student_id) \
            .where("book_id", "==", book_id) \
            .where("status", "==", "Active") \
            .stream()

        for reservation in existing_reservations:
            flash("You already reserved this book.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        reservation_data = {
            "student_id": student_id,
            "book_id": book_id,
            "book_title": book.get("title", ""),
            "reservation_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Active"
        }

        db.collection(RESERVATIONS_COLLECTION).add(reservation_data)

        flash("Book reserved successfully.")

    except Exception as error:
        flash(f"Error reserving book: {error}")

    return redirect(url_for("catalogue_reservation.view_catalogue"))


# SCRUM-690: Cancel reservation
@catalogue_bp.route("/cancel-reservation/<reservation_id>")
def cancel_reservation(reservation_id):
    try:
        reservation_ref = db.collection(RESERVATIONS_COLLECTION).document(reservation_id)
        reservation_doc = reservation_ref.get()

        if not reservation_doc.exists:
            flash("Reservation not found.")
            return redirect(url_for("catalogue_reservation.view_my_reservations"))

        reservation_ref.update({
            "status": "Cancelled"
        })

        flash("Reservation cancelled successfully.")

    except Exception as error:
        flash(f"Error cancelling reservation: {error}")

    return redirect(url_for("catalogue_reservation.view_my_reservations"))


# View student's own reservations
@catalogue_bp.route("/my-reservations")
def view_my_reservations():
    student_id = "S001"  # temporary hardcoded user for Sprint 1
    reservations = []

    try:
        docs = db.collection(RESERVATIONS_COLLECTION) \
            .where("student_id", "==", student_id) \
            .stream()

        for doc in docs:
            reservation = doc.to_dict()
            reservation["reservation_id"] = doc.id
            reservations.append(reservation)

    except Exception as error:
        flash(f"Error loading reservations: {error}")

    return render_template(
        "catalogue_reservation/my_reservations.html",
        reservations=reservations
    )


# SCRUM-16: Request to borrow a book
@catalogue_bp.route("/borrow/<book_id>")
def request_borrow_book(book_id):
    student_id = "S001"  # temporary hardcoded user for Sprint 1

    try:
        book_ref = db.collection(BOOKS_COLLECTION).document(book_id)
        book_doc = book_ref.get()

        if not book_doc.exists:
            flash("Book not found.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        book = book_doc.to_dict()

        available_copies = int(book.get("available_copies", 0))
        status = str(book.get("status", "")).lower()

        if status != "available" or available_copies <= 0:
            flash("This book is unavailable. Please reserve it instead.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        # Prevent duplicate pending borrow request
        existing_requests = db.collection(BORROW_REQUESTS_COLLECTION) \
            .where("student_id", "==", student_id) \
            .where("book_id", "==", book_id) \
            .where("status", "==", "Pending") \
            .stream()

        for borrow_request in existing_requests:
            flash("You already submitted a borrow request for this book.")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        borrow_request_data = {
            "student_id": student_id,
            "book_id": book_id,
            "book_title": book.get("title", ""),
            "request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "borrowing_period": "14 days",
            "status": "Pending"
        }

        db.collection(BORROW_REQUESTS_COLLECTION).add(borrow_request_data)

        flash("Borrow request submitted successfully.")

    except Exception as error:
        flash(f"Error submitting borrow request: {error}")

    return redirect(url_for("catalogue_reservation.view_catalogue"))