from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date, datetime, timedelta

from config.firebase_config import db

catalogue_bp = Blueprint(
    "catalogue_reservation",
    __name__,
    url_prefix="/catalogue"
)

BOOKS_COLLECTION = "books"
RESERVATIONS_COLLECTION = "reservations"
BORROW_REQUESTS_COLLECTION = "borrow_requests"
BORROWING_PERIOD_DAYS = 14
CURRENT_BORROWING_STATUSES = {"approved", "borrowed", "issued", "active"}


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    """Convert supported Firestore or string values into a date."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        cleaned_value = value.strip()
        if not cleaned_value:
            return None

        # Support ISO dates, ISO datetimes and the format already used by
        # this module when writing Firestore records.
        try:
            return datetime.fromisoformat(
                cleaned_value.replace("Z", "+00:00")
            ).date()
        except ValueError:
            pass

        for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(cleaned_value, date_format).date()
            except ValueError:
                continue

    return None


def _today():
    """Return today's date through a small wrapper for deterministic tests."""
    return date.today()


def _remaining_period_text(remaining_days):
    if remaining_days is None:
        return "Due date unavailable"
    if remaining_days > 1:
        return f"{remaining_days} days remaining"
    if remaining_days == 1:
        return "1 day remaining"
    if remaining_days == 0:
        return "Due today"

    overdue_days = abs(remaining_days)
    suffix = "day" if overdue_days == 1 else "days"
    return f"Overdue by {overdue_days} {suffix}"


def _normalise_current_borrowing(document):
    """Convert one approved/issued request into a borrowed-book record."""
    borrowing = document.to_dict() or {}
    status = str(borrowing.get("status", "")).strip().lower()

    if status not in CURRENT_BORROWING_STATUSES:
        return None

    borrowing_period_days = _safe_int(
        borrowing.get("borrowing_period_days", BORROWING_PERIOD_DAYS),
        BORROWING_PERIOD_DAYS,
    )
    if borrowing_period_days <= 0:
        borrowing_period_days = BORROWING_PERIOD_DAYS

    borrow_date = (
        _parse_date(borrowing.get("borrow_date"))
        or _parse_date(borrowing.get("issued_date"))
        or _parse_date(borrowing.get("approval_date"))
        or _parse_date(borrowing.get("approved_date"))
        or _parse_date(borrowing.get("request_date"))
    )
    due_date = _parse_date(borrowing.get("due_date"))

    # SCRUM-677 integration: records created by SCRUM-16 already include
    # borrowing_period_days. When the approval module has not stored a due
    # date, derive it from the approval/borrow/request date.
    if due_date is None and borrow_date is not None:
        due_date = borrow_date + timedelta(days=borrowing_period_days)

    remaining_days = None
    if due_date is not None:
        remaining_days = (due_date - _today()).days

    borrowing["borrowing_id"] = document.id
    borrowing["borrow_date_value"] = borrow_date
    borrowing["due_date_value"] = due_date
    borrowing["borrow_date_display"] = (
        borrow_date.strftime("%Y-%m-%d") if borrow_date else "Not available"
    )
    borrowing["due_date_display"] = (
        due_date.strftime("%Y-%m-%d") if due_date else "Not available"
    )
    borrowing["borrowing_period_days"] = borrowing_period_days
    borrowing["remaining_days"] = remaining_days
    borrowing["remaining_period_text"] = _remaining_period_text(remaining_days)
    borrowing["remaining_period_state"] = (
        "overdue"
        if remaining_days is not None and remaining_days < 0
        else "due-today"
        if remaining_days == 0
        else "active"
    )

    return borrowing


def _matches_search(book, search_keyword):
    if not search_keyword:
        return True

    searchable_fields = (
        book.get("title", ""),
        book.get("author", ""),
        book.get("category", "")
    )

    return any(
        search_keyword in str(field).lower()
        for field in searchable_fields
    )


# SCRUM-44: Setup module + View book catalogue
@catalogue_bp.route("/")
def view_catalogue():
    books = []
    search_keyword = request.args.get("search", "").strip().lower()

    try:
        docs = db.collection(BOOKS_COLLECTION).stream()

        for doc in docs:
            book = doc.to_dict() or {}
            book["book_id"] = doc.id
            book["available_copies"] = _safe_int(
                book.get("available_copies", 0)
            )

            if _matches_search(book, search_keyword):
                books.append(book)

        books.sort(
            key=lambda book: str(book.get("title", "")).lower()
        )

    except Exception as error:
        flash(f"Error loading catalogue: {error}", "danger")

    return render_template(
        "catalogue_reservation/view_catalogue.html",
        books=books,
        search_keyword=search_keyword,
        page_title="Book Catalogue",
        page_description=(
            "Browse, borrow, or reserve books "
            "from the LibTrack library catalogue."
        ),
        available_only=False
    )


# SCRUM-684: Display all available books
@catalogue_bp.route("/available")
def view_available_books():
    books = []
    search_keyword = request.args.get("search", "").strip().lower()

    try:
        docs = db.collection(BOOKS_COLLECTION).stream()

        for doc in docs:
            book = doc.to_dict() or {}
            book["book_id"] = doc.id

            status = str(book.get("status", "")).strip().lower()
            available_copies = _safe_int(
                book.get("available_copies", 0)
            )

            book["available_copies"] = available_copies

            is_available = (
                status == "available"
                and available_copies > 0
            )

            if is_available and _matches_search(book, search_keyword):
                books.append(book)

        books.sort(
            key=lambda book: str(book.get("title", "")).lower()
        )

    except Exception as error:
        flash(f"Error loading available books: {error}", "danger")

    return render_template(
        "catalogue_reservation/view_catalogue.html",
        books=books,
        search_keyword=search_keyword,
        page_title="Available Books",
        page_description=(
            "View books that currently have at least one copy "
            "available for borrowing."
        ),
        available_only=True
    )


# SCRUM-685: View current availability status and book details
def _load_selected_book(book_id):
    """Load and normalise one selected book from Firestore."""
    book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()

    if not book_doc.exists:
        return None

    book = book_doc.to_dict() or {}
    book["book_id"] = book_doc.id

    available_copies = _safe_int(
        book.get("available_copies", 0)
    )
    total_copies = _safe_int(
        book.get("total_copies", 0)
    )
    stored_status = str(
        book.get("status", "")
    ).strip().lower()

    is_available = (
        stored_status == "available"
        and available_copies > 0
    )

    book["available_copies"] = available_copies
    book["total_copies"] = total_copies
    book["current_status"] = (
        "Available" if is_available else "Unavailable"
    )

    return book, is_available


def _render_selected_book_details(book_id):
    """Render the shared book-details interface for one selected book."""
    try:
        selected_book = _load_selected_book(book_id)

        if selected_book is None:
            flash("Book not found.", "danger")
            return redirect(
                url_for("catalogue_reservation.view_catalogue")
            )

        book, is_available = selected_book

        return render_template(
            "catalogue_reservation/book_details.html",
            book=book,
            is_available=is_available
        )

    except Exception as error:
        flash(f"Error loading book details: {error}", "danger")
        return redirect(
            url_for("catalogue_reservation.view_catalogue")
        )


@catalogue_bp.route("/details/<book_id>")
def view_book_details(book_id):
    """Display the complete details and current availability of a book."""
    return _render_selected_book_details(book_id)


@catalogue_bp.route("/availability/<book_id>")
def view_book_availability(book_id):
    """Keep the previous SCRUM-685 URL working for compatibility."""
    return _render_selected_book_details(book_id)


# SCRUM-689: Reserve an unavailable book
@catalogue_bp.route("/reserve/<book_id>", methods=["GET", "POST"])
def reserve_book(book_id):
    """Allow a student to reserve a book that is currently unavailable.

    GET displays a confirmation page. POST validates the book again and
    creates one active reservation when no duplicate active reservation
    exists for the same student and book.
    """
    student_id = session.get("student_id", "S001")

    try:
        book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()

        if not book_doc.exists:
            flash("Book not found.", "danger")
            return redirect(url_for("catalogue_reservation.view_catalogue"))

        book = book_doc.to_dict() or {}
        book["book_id"] = book_doc.id
        book["available_copies"] = _safe_int(
            book.get("available_copies", 0)
        )

        stored_status = str(book.get("status", "")).strip().lower()
        is_available = (
            stored_status == "available"
            and book["available_copies"] > 0
        )

        if is_available:
            flash(
                "This book is currently available. "
                "Please submit a borrowing request instead.",
                "info"
            )
            return redirect(
                url_for(
                    "catalogue_reservation.view_book_availability",
                    book_id=book_id
                )
            )

        existing_reservations = (
            db.collection(RESERVATIONS_COLLECTION)
            .where("student_id", "==", student_id)
            .where("book_id", "==", book_id)
            .where("status", "==", "Active")
            .stream()
        )

        if any(True for _ in existing_reservations):
            flash("You already have an active reservation for this book.", "info")
            return redirect(
                url_for("catalogue_reservation.view_my_reservations")
            )

        if request.method == "GET":
            return render_template(
                "catalogue_reservation/reserve_book.html",
                book=book
            )

        reservation_data = {
            "student_id": student_id,
            "book_id": book_id,
            "book_title": book.get("title", "Untitled Book"),
            "reservation_date": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "status": "Active"
        }

        db.collection(RESERVATIONS_COLLECTION).add(reservation_data)

        flash(
            f"'{reservation_data['book_title']}' was reserved successfully.",
            "success"
        )
        return redirect(
            url_for("catalogue_reservation.view_my_reservations")
        )

    except Exception as error:
        flash(f"Error reserving book: {error}", "danger")
        return redirect(url_for("catalogue_reservation.view_catalogue"))


# SCRUM-690: Cancel reservation
@catalogue_bp.route(
    "/cancel-reservation/<reservation_id>",
    methods=["GET", "POST"]
)
def cancel_reservation(reservation_id):
    """Allow the current student to cancel one active reservation.

    GET displays a simple confirmation page. POST validates the reservation
    again before updating its status in Firestore.
    """
    student_id = session.get("student_id", "S001")

    try:
        reservation_ref = (
            db.collection(RESERVATIONS_COLLECTION)
            .document(reservation_id)
        )
        reservation_doc = reservation_ref.get()

        if not reservation_doc.exists:
            flash("Reservation not found.", "danger")
            return redirect(
                url_for("catalogue_reservation.view_my_reservations")
            )

        reservation = reservation_doc.to_dict() or {}
        reservation["reservation_id"] = reservation_doc.id

        # A student may only cancel their own reservation.
        if reservation.get("student_id") != student_id:
            flash("Reservation not found.", "danger")
            return redirect(
                url_for("catalogue_reservation.view_my_reservations")
            )

        current_status = str(
            reservation.get("status", "")
        ).strip().lower()

        if current_status != "active":
            flash(
                "Only an active reservation can be cancelled.",
                "info"
            )
            return redirect(
                url_for("catalogue_reservation.view_my_reservations")
            )

        if request.method == "GET":
            return render_template(
                "catalogue_reservation/cancel_reservation.html",
                reservation=reservation
            )

        cancellation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        reservation_ref.update({
            "status": "Cancelled",
            "cancellation_date": cancellation_date
        })

        flash(
            f"Reservation for '{reservation.get('book_title', 'the book')}' "
            "was cancelled successfully.",
            "success"
        )

    except Exception as error:
        flash(f"Error cancelling reservation: {error}", "danger")

    return redirect(
        url_for("catalogue_reservation.view_my_reservations")
    )


# View student's own reservations
@catalogue_bp.route("/my-reservations")
def view_my_reservations():
    student_id = session.get("student_id", "S001")
    reservations = []

    try:
        docs = (
            db.collection(RESERVATIONS_COLLECTION)
            .where("student_id", "==", student_id)
            .stream()
        )

        for doc in docs:
            reservation = doc.to_dict() or {}
            reservation["reservation_id"] = doc.id
            reservations.append(reservation)

        # Show active reservations before cancelled ones, then newest first.
        reservations.sort(
            key=lambda reservation: (
                str(reservation.get("status", "")).lower() != "active",
                str(reservation.get("reservation_date", ""))
            )
        )

    except Exception as error:
        flash(f"Error loading reservations: {error}", "danger")

    return render_template(
        "catalogue_reservation/my_reservations.html",
        reservations=reservations
    )


# SCRUM-16, SCRUM-36, SCRUM-691 and SCRUM-692:
# Request to borrow a book, display the borrowing period, and validate requests.
@catalogue_bp.route("/borrow/<book_id>", methods=["GET", "POST"])
def request_borrow_book(book_id):
    """Display and submit a borrowing request for an available book.

    GET validates the selected book and displays the 14-day borrowing period
    before confirmation. POST repeats the validations and stores one pending
    request in Firestore.
    """
    student_id = session.get("student_id", "S001")

    try:
        book_doc = db.collection(BOOKS_COLLECTION).document(book_id).get()

        if not book_doc.exists:
            flash("Book not found.", "danger")
            return redirect(
                url_for("catalogue_reservation.view_catalogue")
            )

        book = book_doc.to_dict() or {}
        book["book_id"] = book_doc.id
        book["available_copies"] = _safe_int(
            book.get("available_copies", 0)
        )

        stored_status = str(
            book.get("status", "")
        ).strip().lower()
        is_available = (
            stored_status == "available"
            and book["available_copies"] > 0
        )

        # SCRUM-691: Unavailable books cannot be borrowed.
        if not is_available:
            flash(
                "This book is unavailable. Please reserve it instead.",
                "info"
            )
            return redirect(
                url_for(
                    "catalogue_reservation.view_book_details",
                    book_id=book_id
                )
            )

        # SCRUM-692: Prevent a second pending request for the same book.
        existing_requests = (
            db.collection(BORROW_REQUESTS_COLLECTION)
            .where("student_id", "==", student_id)
            .where("book_id", "==", book_id)
            .where("status", "==", "Pending")
            .stream()
        )

        if any(True for _ in existing_requests):
            flash(
                "You already submitted a pending borrow request "
                "for this book.",
                "info"
            )
            return redirect(
                url_for(
                    "catalogue_reservation.view_book_details",
                    book_id=book_id
                )
            )

        # SCRUM-36: Show the borrowing period before any data is created.
        if request.method == "GET":
            return render_template(
                "catalogue_reservation/borrow_book.html",
                book=book,
                borrowing_period_days=BORROWING_PERIOD_DAYS
            )

        # SCRUM-16: Store the confirmed borrowing request in Firestore.
        request_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        borrow_request_data = {
            "student_id": student_id,
            "book_id": book_id,
            "book_title": book.get("title", "Untitled Book"),
            "request_date": request_date,
            "borrowing_period": f"{BORROWING_PERIOD_DAYS} days",
            "borrowing_period_days": BORROWING_PERIOD_DAYS,
            "status": "Pending"
        }

        db.collection(BORROW_REQUESTS_COLLECTION).add(
            borrow_request_data
        )

        flash(
            f"Borrow request for '{borrow_request_data['book_title']}' "
            "was submitted successfully.",
            "success"
        )
        return redirect(
            url_for(
                "catalogue_reservation.view_book_details",
                book_id=book_id
            )
        )

    except Exception as error:
        flash(f"Error submitting borrow request: {error}", "danger")
        return redirect(
            url_for("catalogue_reservation.view_catalogue")
        )


# SCRUM-675 and SCRUM-677: View currently borrowed books and remaining period
@catalogue_bp.route("/my-borrowed-books")
def view_currently_borrowed_books():
    """Display the current student's approved or issued borrowing records."""
    student_id = session.get("student_id", "S001")
    borrowed_books = []

    try:
        documents = (
            db.collection(BORROW_REQUESTS_COLLECTION)
            .where("student_id", "==", student_id)
            .stream()
        )

        for document in documents:
            borrowing = _normalise_current_borrowing(document)
            if borrowing is not None:
                borrowed_books.append(borrowing)

        # Books due first are displayed first. Records without a due date are
        # placed at the end so valid remaining-period information is prominent.
        borrowed_books.sort(
            key=lambda borrowing: (
                borrowing.get("due_date_value") is None,
                borrowing.get("due_date_value") or date.max,
                str(borrowing.get("book_title", "")).lower(),
            )
        )

    except Exception as error:
        flash(f"Error loading borrowed books: {error}", "danger")

    return render_template(
        "catalogue_reservation/currently_borrowed_books.html",
        borrowed_books=borrowed_books,
    )

