from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from config.firebase_config import COLLECTION_BOOKS, db

from modules.authentication.decorators import (
    librarian_required,
)


book_bp = Blueprint(
    "book_catalogue",
    __name__,
    url_prefix="/books",
    template_folder=".",
)

COPY_STATUSES = (
    "Available",
    "Borrowed",
    "Reserved",
    "Lost",
    "Damaged",
)

BOOK_INACTIVE_REASONS = (
    "Outdated Content",
    "Unsuitable Content",
    "Incorrect Information",
    "Temporarily Withdrawn",
    "Under Review",
)


def _current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _isbn_already_exists(isbn, exclude_book_id=None):
    """Return True when another book already uses the ISBN."""
    matching_books = (
        db.collection(COLLECTION_BOOKS)
        .where("isbn", "==", isbn)
        .limit(10)
        .stream()
    )

    for book_doc in matching_books:
        document_id = getattr(book_doc, "id", None)
        if exclude_book_id is None or document_id != exclude_book_id:
            return True

    return False


def _generate_initial_book_copies(book_reference, quantity):
    """Create one physical-copy record for every initial copy."""
    copies_collection = book_reference.collection("copies")

    for copy_number in range(1, quantity + 1):
        copy_id = f"COPY-{book_reference.id.upper()}-{copy_number:03d}"
        copies_collection.document(copy_id).set(
            {
                "copy_id": copy_id,
                "book_id": book_reference.id,
                "copy_number": copy_number,
                "status": "Available",
                "condition": "Good",
                "created_at": _current_timestamp(),
            }
        )


def _get_book_copies(book_id):
    """Return every physical copy that belongs to a book."""
    copies_documents = (
        db.collection(COLLECTION_BOOKS)
        .document(book_id)
        .collection("copies")
        .stream()
    )

    copies = []
    for document in copies_documents:
        copy_record = document.to_dict() or {}
        copy_record["document_id"] = document.id
        copies.append(copy_record)

    copies.sort(key=lambda copy_record: int(copy_record.get("copy_number", 0)))
    return copies


def _get_book_copy_by_id(book_id, copy_id):
    """Return one physical copy, or None when it does not exist."""
    copy_document = (
        db.collection(COLLECTION_BOOKS)
        .document(book_id)
        .collection("copies")
        .document(copy_id)
        .get()
    )

    if not copy_document.exists:
        return None

    copy_record = copy_document.to_dict() or {}
    copy_record["document_id"] = copy_document.id
    return copy_record


def _get_next_copy_number(copies):
    if not copies:
        return 1

    copy_numbers = [
        int(copy_record.get("copy_number", 0))
        for copy_record in copies
    ]
    return max(copy_numbers) + 1


def _calculate_copy_summary(copies):
    summary = {
        "total": len(copies),
        "available": 0,
        "borrowed": 0,
        "reserved": 0,
        "damaged": 0,
        "lost": 0,
    }

    for copy_record in copies:
        status = str(copy_record.get("status", "")).strip().lower()
        if status in summary and status != "total":
            summary[status] += 1

    return summary


def _sync_book_inventory_from_copies(book_id):
    """Synchronise aggregate borrowing availability from copy records."""
    copies = _get_book_copies(book_id)
    copy_summary = _calculate_copy_summary(copies)
    inventory_status = (
        "Available" if copy_summary["available"] > 0 else "Unavailable"
    )

    db.collection(COLLECTION_BOOKS).document(book_id).update(
        {
            "total_copies": copy_summary["total"],
            "available_copies": copy_summary["available"],
            "status": inventory_status,
            "updated_at": _current_timestamp(),
        }
    )
    return copy_summary


def _is_book_active(book):
    """Support both current and older catalogue visibility fields."""
    visible = book.get("is_visible_to_students")
    if isinstance(visible, bool):
        return visible

    catalogue_status = str(book.get("catalogue_status", "Active")).lower()
    return catalogue_status not in {"inactive", "unavailable"}


# ============================================================
# DISPLAY ALL BOOK RECORDS
# ============================================================

@book_bp.route("/", methods=["GET"])
@librarian_required
def manage_books():
    books = []

    for document in db.collection(COLLECTION_BOOKS).stream():
        book = document.to_dict() or {}
        book["book_id"] = document.id
        book["catalogue_status"] = (
            "Active" if _is_book_active(book) else "Inactive"
        )
        books.append(book)

    books.sort(key=lambda book: str(book.get("title", "")).lower())
    return render_template("manage_books.html", books=books)


# ============================================================
# SCRUM-12: ADD NEW BOOK
# ============================================================

@book_bp.route("/add", methods=["GET", "POST"])
@librarian_required
def add_book():
    form_data = {}

    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "author": request.form.get("author", "").strip(),
            "isbn": request.form.get("isbn", "").strip(),
            "category": request.form.get("category", "").strip(),
            "publisher": request.form.get("publisher", "").strip(),
            "publication_year": request.form.get(
                "publication_year", ""
            ).strip(),
            "description": request.form.get("description", "").strip(),
            "total_copies": request.form.get("total_copies", "").strip(),
        }

        required_fields = {
            "title": "Book title",
            "author": "Author",
            "isbn": "ISBN",
            "category": "Category",
            "total_copies": "Total copies",
        }
        missing_fields = [
            label
            for field_name, label in required_fields.items()
            if not form_data[field_name]
        ]

        if missing_fields:
            return render_template(
                "add_book.html",
                form_data=form_data,
                error="Please fill in all required fields.",
            ), 400

        try:
            total_copies = int(form_data["total_copies"])
        except ValueError:
            return render_template(
                "add_book.html",
                form_data=form_data,
                error="Total copies must be a valid whole number.",
            ), 400

        if total_copies < 1:
            return render_template(
                "add_book.html",
                form_data=form_data,
                error="Total copies must be at least 1.",
            ), 400

        year_error = _validate_publication_year(form_data["publication_year"])
        if year_error:
            return render_template(
                "add_book.html",
                form_data=form_data,
                error=year_error,
            ), 400

        if _isbn_already_exists(form_data["isbn"]):
            return render_template(
                "add_book.html",
                form_data=form_data,
                error="A book with this ISBN already exists.",
            ), 400

        book_data = {
            "title": form_data["title"],
            "author": form_data["author"],
            "isbn": form_data["isbn"],
            "category": form_data["category"],
            "publisher": form_data["publisher"],
            "publication_year": form_data["publication_year"],
            "description": form_data["description"],
            "total_copies": total_copies,
            "available_copies": total_copies,
            "status": "Available",
            "catalogue_status": "Active",
            "is_visible_to_students": True,
            "catalogue_inactive_reason": "",
            "created_at": _current_timestamp(),
        }

        _, book_reference = db.collection(COLLECTION_BOOKS).add(book_data)
        _generate_initial_book_copies(book_reference, total_copies)

        flash(
            (
                "Book record added successfully. "
                f"{total_copies} unique copy IDs were generated."
            ),
            "success",
        )
        return redirect(url_for("book_catalogue.add_book"))

    return render_template("add_book.html", form_data=form_data)


def get_book_by_id(book_id):
    """Return one book using its Firestore document ID."""
    book_doc = db.collection(COLLECTION_BOOKS).document(book_id).get()
    if not book_doc.exists:
        return None

    book = book_doc.to_dict() or {}
    book["book_id"] = book_doc.id
    book["catalogue_status"] = (
        "Active" if _is_book_active(book) else "Inactive"
    )
    return book


# ============================================================
# SCRUM-898: LIBRARIAN BOOK DETAILS AND COPY SUMMARY
# ============================================================

@book_bp.route("/details/<book_id>", methods=["GET"])
@librarian_required
def librarian_book_details(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    copies = _get_book_copies(book_id)
    return render_template(
        "librarian_book_details.html",
        book=book,
        copies=copies,
        copy_summary=_calculate_copy_summary(copies),
    )


# ============================================================
# DEACTIVATE / ACTIVATE WHOLE BOOK IN STUDENT CATALOGUE
# ============================================================

@book_bp.route("/catalogue/deactivate/<book_id>", methods=["GET", "POST"])
@book_bp.route("/catalogue/unavailable/<book_id>", methods=["GET", "POST"])
@librarian_required
def deactivate_book(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        if reason not in BOOK_INACTIVE_REASONS:
            return render_template(
                "deactivate_book.html",
                book=book,
                inactive_reasons=BOOK_INACTIVE_REASONS,
                error="Please select a valid reason for deactivating the book.",
            ), 400

        current_time = _current_timestamp()
        db.collection(COLLECTION_BOOKS).document(book_id).update(
            {
                "catalogue_status": "Inactive",
                "is_visible_to_students": False,
                "catalogue_inactive_reason": reason,
                "catalogue_deactivated_at": current_time,
                "updated_at": current_time,
            }
        )
        flash(
            (
                f"{book.get('title', 'The book')} was deactivated "
                "and hidden from the student catalogue."
            ),
            "success",
        )
        return redirect(
            url_for("book_catalogue.librarian_book_details", book_id=book_id)
        )

    return render_template(
        "deactivate_book.html",
        book=book,
        inactive_reasons=BOOK_INACTIVE_REASONS,
    )


@book_bp.route("/catalogue/activate/<book_id>", methods=["POST"])
@book_bp.route("/catalogue/restore/<book_id>", methods=["POST"])
@librarian_required
def activate_book(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    if _is_book_active(book):
        return "This book is already active in the student catalogue.", 400

    current_time = _current_timestamp()
    db.collection(COLLECTION_BOOKS).document(book_id).update(
        {
            "catalogue_status": "Active",
            "is_visible_to_students": True,
            "catalogue_inactive_reason": "",
            "catalogue_unavailable_reason": "",
            "catalogue_activated_at": current_time,
            "updated_at": current_time,
        }
    )
    flash(
        (
            f"{book.get('title', 'The book')} was activated "
            "and is now visible in the student catalogue."
        ),
        "success",
    )
    return redirect(
        url_for("book_catalogue.librarian_book_details", book_id=book_id)
    )


# ============================================================
# SCRUM-695: UPDATE INDIVIDUAL PHYSICAL COPY STATUS
# ============================================================

@book_bp.route(
    "/copies/status/<book_id>/<copy_id>",
    methods=["GET", "POST"],
)
@librarian_required
def update_copy_status(book_id, copy_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    copy_record = _get_book_copy_by_id(book_id, copy_id)
    if copy_record is None:
        return "Physical book copy not found.", 404

    if request.method == "POST":
        selected_status = request.form.get("status", "").strip()
        if selected_status not in COPY_STATUSES:
            return render_template(
                "update_copy_status.html",
                book=book,
                copy_record=copy_record,
                copy_statuses=COPY_STATUSES,
                error="Please select a valid copy status.",
            ), 400

        current_time = _current_timestamp()
        copy_updates = {
            "status": selected_status,
            "updated_at": current_time,
        }

        if selected_status in {"Available", "Borrowed", "Reserved"}:
            copy_updates["condition"] = "Good"
        elif selected_status == "Damaged":
            copy_updates["condition"] = "Damaged"
        elif selected_status == "Lost":
            copy_updates["condition"] = "Lost"

        (
            db.collection(COLLECTION_BOOKS)
            .document(book_id)
            .collection("copies")
            .document(copy_id)
            .update(copy_updates)
        )
        _sync_book_inventory_from_copies(book_id)

        flash(
            f"{copy_id} status was updated to {selected_status} successfully.",
            "success",
        )
        return redirect(
            url_for("book_catalogue.librarian_book_details", book_id=book_id)
        )

    return render_template(
        "update_copy_status.html",
        book=book,
        copy_record=copy_record,
        copy_statuses=COPY_STATUSES,
    )


# ============================================================
# SCRUM-688: RESTORE REPAIRED PHYSICAL COPY
# ============================================================

@book_bp.route(
    "/copies/restore/<book_id>/<copy_id>",
    methods=["POST"],
)
@librarian_required
def restore_damaged_copy(book_id, copy_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    copy_record = _get_book_copy_by_id(book_id, copy_id)
    if copy_record is None:
        return "Physical book copy not found.", 404

    current_status = str(copy_record.get("status", "")).strip().lower()
    if current_status != "damaged":
        return "Only damaged physical copies can be restored.", 400

    current_time = _current_timestamp()
    (
        db.collection(COLLECTION_BOOKS)
        .document(book_id)
        .collection("copies")
        .document(copy_id)
        .update(
            {
                "status": "Available",
                "condition": "Good",
                "restored_at": current_time,
                "updated_at": current_time,
            }
        )
    )
    _sync_book_inventory_from_copies(book_id)

    flash(
        f"{copy_id} was restored successfully and is now available for borrowing.",
        "success",
    )
    return redirect(
        url_for("book_catalogue.librarian_book_details", book_id=book_id)
    )


def _validate_publication_year(publication_year):
    """Validate an optional four-digit publication year."""
    if not publication_year:
        return None
    if not publication_year.isdigit():
        return "Publication year must be a valid four-digit year."

    year = int(publication_year)
    current_year = datetime.now().year
    if len(publication_year) != 4 or year < 1000 or year > current_year:
        return f"Publication year must be between 1000 and {current_year}."
    return None


# ============================================================
# SCRUM-40: EDIT BOOK DETAILS
# ============================================================

@book_bp.route("/edit/<book_id>", methods=["GET", "POST"])
@librarian_required
def edit_book(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    if request.method == "POST":
        submitted_book = {
            **book,
            "title": request.form.get("title", "").strip(),
            "author": request.form.get("author", "").strip(),
            "category": request.form.get("category", "").strip(),
            "isbn": request.form.get("isbn", "").strip(),
            "publisher": request.form.get("publisher", "").strip(),
            "publication_year": request.form.get(
                "publication_year", ""
            ).strip(),
            "description": request.form.get("description", "").strip(),
        }

        required_fields = {
            "title": "Book title",
            "author": "Author",
            "isbn": "ISBN",
            "category": "Category",
        }
        missing_fields = [
            label
            for field_name, label in required_fields.items()
            if not submitted_book[field_name]
        ]

        if missing_fields:
            return render_template(
                "edit_book.html",
                book=submitted_book,
                error="Please fill in all required fields.",
            ), 400

        year_error = _validate_publication_year(
            submitted_book["publication_year"]
        )
        if year_error:
            return render_template(
                "edit_book.html", book=submitted_book, error=year_error
            ), 400

        if _isbn_already_exists(
            submitted_book["isbn"], exclude_book_id=book_id
        ):
            return render_template(
                "edit_book.html",
                book=submitted_book,
                error="A book with this ISBN already exists.",
            ), 400

        db.collection(COLLECTION_BOOKS).document(book_id).update(
            {
                "title": submitted_book["title"],
                "author": submitted_book["author"],
                "category": submitted_book["category"],
                "isbn": submitted_book["isbn"],
                "publisher": submitted_book["publisher"],
                "publication_year": submitted_book["publication_year"],
                "description": submitted_book["description"],
                "updated_at": _current_timestamp(),
            }
        )
        flash("Book details updated successfully.", "success")
        return redirect(url_for("book_catalogue.manage_books"))

    return render_template("edit_book.html", book=book)


# ============================================================
# SCRUM-895: ADD ADDITIONAL PHYSICAL BOOK COPIES
# ============================================================

@book_bp.route("/copies/add/<book_id>", methods=["GET", "POST"])
@librarian_required
def add_book_copies(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    copies = _get_book_copies(book_id)

    if request.method == "POST":
        quantity_text = request.form.get("quantity", "").strip()
        try:
            quantity = int(quantity_text)
        except ValueError:
            return render_template(
                "add_book_copies.html",
                book=book,
                copies=copies,
                error=(
                    "The number of additional copies must be a valid whole number."
                ),
            ), 400

        if quantity < 1:
            return render_template(
                "add_book_copies.html",
                book=book,
                copies=copies,
                error="The number of additional copies must be at least 1.",
            ), 400

        next_copy_number = _get_next_copy_number(copies)
        book_reference = db.collection(COLLECTION_BOOKS).document(book_id)
        copies_collection = book_reference.collection("copies")

        for position in range(quantity):
            copy_number = next_copy_number + position
            copy_id = f"COPY-{book_id.upper()}-{copy_number:03d}"
            copies_collection.document(copy_id).set(
                {
                    "copy_id": copy_id,
                    "book_id": book_id,
                    "copy_number": copy_number,
                    "status": "Available",
                    "condition": "Good",
                    "created_at": _current_timestamp(),
                }
            )

        _sync_book_inventory_from_copies(book_id)
        flash(
            f"{quantity} additional physical book copies were added successfully.",
            "success",
        )
        return redirect(
            url_for("book_catalogue.librarian_book_details", book_id=book_id)
        )

    return render_template("add_book_copies.html", book=book, copies=copies)


# ============================================================
# SCRUM-704: DELETE COMPLETE BOOK RECORD
# ============================================================

@book_bp.route("/delete/<book_id>", methods=["GET", "POST"])
@librarian_required
def delete_book(book_id):
    book = get_book_by_id(book_id)
    if book is None:
        return "Book record not found.", 404

    if request.method == "GET":
        return render_template("delete_book.html", book=book)

    book_reference = db.collection(COLLECTION_BOOKS).document(book_id)
    for copy_document in book_reference.collection("copies").stream():
        copy_document.reference.delete()
    book_reference.delete()

    flash("Book record deleted successfully.", "success")
    return redirect(url_for("book_catalogue.manage_books"))
