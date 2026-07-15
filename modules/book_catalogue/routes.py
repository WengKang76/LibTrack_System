from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from config.firebase_config import COLLECTION_BOOKS, db


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


def _isbn_already_exists(isbn, exclude_book_id=None):
    """
    Check whether an ISBN is already used by another book.

    exclude_book_id allows the current book to keep its ISBN
    when its details are edited.
    """
    matching_books = (
        db.collection(COLLECTION_BOOKS)
        .where("isbn", "==", isbn)
        .limit(10)
        .stream()
    )

    for book_doc in matching_books:
        document_id = getattr(book_doc, "id", None)

        if (
            exclude_book_id is None
            or document_id != exclude_book_id
        ):
            return True

    return False


def _generate_initial_book_copies(
    book_reference,
    quantity,
):
    """
    Generate one physical-copy record for every copy
    of a newly added book.
    """
    copies_collection = book_reference.collection("copies")

    

    for copy_number in range(1, quantity + 1):
        copy_id = (
            f"COPY-{book_reference.id.upper()}-"
            f"{copy_number:03d}"
        )

        copy_data = {
            "copy_id": copy_id,
            "book_id": book_reference.id,
            "copy_number": copy_number,
            "status": "Available",
            "condition": "Good",
            "created_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        copies_collection.document(copy_id).set(
            copy_data
        )

def _get_book_copies(book_id):
    """
    Retrieve all physical copies belonging to one book.
    """
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

    copies.sort(
        key=lambda copy_record: copy_record.get(
            "copy_number",
            0,
        )
    )

    return copies

def _get_book_copy_by_id(book_id, copy_id):
    """
    Retrieve one physical copy belonging to a selected book.
    """
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
    """
    Find the next copy number based on the existing copies.
    """
    if not copies:
        return 1

    copy_numbers = [
        int(copy_record.get("copy_number", 0))
        for copy_record in copies
    ]

    return max(copy_numbers) + 1


def _calculate_copy_summary(copies):
    """
    Calculate the number of copies for each status.
    """
    summary = {
        "total": len(copies),
        "available": 0,
        "borrowed": 0,
        "reserved": 0,
        "damaged": 0,
        "lost": 0,
    }

    for copy_record in copies:
        status = copy_record.get(
            "status",
            "",
        ).strip().lower()

        if status == "available":
            summary["available"] += 1

        elif status == "borrowed":
            summary["borrowed"] += 1

        elif status == "reserved":
            summary["reserved"] += 1

        elif status == "damaged":
            summary["damaged"] += 1

        elif status == "lost":
            summary["lost"] += 1

    return summary

# ============================================================
# DISPLAY ALL BOOK RECORDS
# ============================================================

@book_bp.route("/", methods=["GET"])
def manage_books():
    book_documents = db.collection(
        COLLECTION_BOOKS
    ).stream()

    books = []

    for document in book_documents:
        book = document.to_dict() or {}
        book["book_id"] = document.id
        books.append(book)

    books.sort(
        key=lambda book: book.get(
            "title",
            "",
        ).lower()
    )

    return render_template(
        "manage_books.html",
        books=books,
    )

# ============================================================
# SCRUM-12: ADD NEW BOOK
# ============================================================

@book_bp.route("/add", methods=["GET", "POST"])
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
                "publication_year",
                "",
            ).strip(),
            "total_copies": request.form.get(
                "total_copies",
                "",
            ).strip(),
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

        publication_year = form_data["publication_year"]

        if publication_year:
            if not publication_year.isdigit():
                return render_template(
                    "add_book.html",
                    form_data=form_data,
                    error=(
                        "Publication year must be a valid "
                        "four-digit year."
                    ),
                ), 400

            current_year = datetime.now().year
            year = int(publication_year)

            if (
                len(publication_year) != 4
                or year < 1000
                or year > current_year
            ):
                return render_template(
                    "add_book.html",
                    form_data=form_data,
                    error=(
                        f"Publication year must be between "
                        f"1000 and {current_year}."
                    ),
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
            "publication_year": form_data[
                "publication_year"
            ],
            "total_copies": total_copies,
            "available_copies": total_copies,
            "status": "Available",
            "created_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }

        _, book_reference = db.collection(
            COLLECTION_BOOKS
        ).add(book_data)

        _generate_initial_book_copies(
            book_reference,
            total_copies,
        )

        flash(
            (
                "Book record added successfully. "
                f"{total_copies} unique copy IDs "
                "were generated."
            ),
            "success",
        )

        return redirect(
            url_for("book_catalogue.add_book")
        )

    return render_template(
        "add_book.html",
        form_data=form_data,
    )


# ============================================================
# SCRUM-40: EDIT BOOK DETAILS
# ============================================================

def get_book_by_id(book_id):
    """Retrieve one book using its Firebase document ID."""
    book_doc = db.collection(COLLECTION_BOOKS).document(book_id).get()

    if not book_doc.exists:
        return None

    book = book_doc.to_dict()
    book["book_id"] = book_doc.id

    return book

# ============================================================
# SCRUM-898: VIEW LIBRARIAN BOOK DETAILS AND COPY SUMMARY
# ============================================================

@book_bp.route("/details/<book_id>", methods=["GET"])
def librarian_book_details(book_id):
    book = get_book_by_id(book_id)

    if book is None:
        return "Book record not found.", 404

    copies = _get_book_copies(book_id)

    copy_summary = _calculate_copy_summary(copies)

    return render_template(
        "librarian_book_details.html",
        book=book,
        copies=copies,
        copy_summary=copy_summary,
    )

# ============================================================
# SCRUM-695: UPDATE INDIVIDUAL PHYSICAL COPY STATUS
# ============================================================

@book_bp.route(
    "/copies/status/<book_id>/<copy_id>",
    methods=["GET", "POST"],
)
def update_copy_status(book_id, copy_id):
    book = get_book_by_id(book_id)

    if book is None:
        return "Book record not found.", 404

    copy_record = _get_book_copy_by_id(
        book_id,
        copy_id,
    )

    if copy_record is None:
        return "Physical book copy not found.", 404

    if request.method == "POST":
        selected_status = request.form.get(
            "status",
            "",
        ).strip()

        if selected_status not in COPY_STATUSES:
            return render_template(
                "update_copy_status.html",
                book=book,
                copy_record=copy_record,
                copy_statuses=COPY_STATUSES,
                error="Please select a valid copy status.",
            ), 400

        copy_reference = (
            db.collection(COLLECTION_BOOKS)
            .document(book_id)
            .collection("copies")
            .document(copy_id)
        )

        copy_reference.update(
            {
                "status": selected_status,
                "updated_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

        flash(
            (
                f"{copy_id} status was updated "
                f"to {selected_status} successfully."
            ),
            "success",
        )

        return redirect(
            url_for(
                "book_catalogue.librarian_book_details",
                book_id=book_id,
            )
        )

    return render_template(
        "update_copy_status.html",
        book=book,
        copy_record=copy_record,
        copy_statuses=COPY_STATUSES,
    )

def _validate_publication_year(publication_year):
    """
    Validate an optional publication year.

    Empty year is allowed because publication year is optional.
    """
    if not publication_year:
        return None

    if not publication_year.isdigit():
        return "Publication year must be a valid four-digit year."

    year = int(publication_year)
    current_year = datetime.now().year

    if len(publication_year) != 4 or year < 1000 or year > current_year:
        return f"Publication year must be between 1000 and {current_year}."

    return None


@book_bp.route("/edit/<book_id>", methods=["GET", "POST"])
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
                "publication_year",
                "",
            ).strip(),
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
                "edit_book.html",
                book=submitted_book,
                error=year_error,
            ), 400

        if _isbn_already_exists(
            submitted_book["isbn"],
            exclude_book_id=book_id,
        ):
            return render_template(
                "edit_book.html",
                book=submitted_book,
                error="A book with this ISBN already exists.",
            ), 400

        updated_book = {
            "title": submitted_book["title"],
            "author": submitted_book["author"],
            "category": submitted_book["category"],
            "isbn": submitted_book["isbn"],
            "publisher": submitted_book["publisher"],
            "publication_year": submitted_book["publication_year"],
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        db.collection(COLLECTION_BOOKS).document(book_id).update(
            updated_book
        )

        flash("Book details updated successfully.", "success")

        return redirect(
            url_for("book_catalogue.manage_books")
        )

    return render_template("edit_book.html", book=book)

# ============================================================
# SCRUM-895: ADD ADDITIONAL PHYSICAL BOOK COPIES
# ============================================================

@book_bp.route(
    "/copies/add/<book_id>",
    methods=["GET", "POST"],
)
def add_book_copies(book_id):
    book = get_book_by_id(book_id)

    if book is None:
        return "Book record not found.", 404

    copies = _get_book_copies(book_id)

    if request.method == "POST":
        quantity_text = request.form.get(
            "quantity",
            "",
        ).strip()

        try:
            quantity = int(quantity_text)

        except ValueError:
            return render_template(
                "add_book_copies.html",
                book=book,
                copies=copies,
                error=(
                    "The number of additional copies "
                    "must be a valid whole number."
                ),
            ), 400

        if quantity < 1:
            return render_template(
                "add_book_copies.html",
                book=book,
                copies=copies,
                error=(
                    "The number of additional copies "
                    "must be at least 1."
                ),
            ), 400

        next_copy_number = _get_next_copy_number(
            copies
        )

        book_reference = (
            db.collection(COLLECTION_BOOKS)
            .document(book_id)
        )

        copies_collection = book_reference.collection(
            "copies"
        )

        generated_copy_ids = []

        for position in range(quantity):
            copy_number = (
                next_copy_number + position
            )

            copy_id = (
                f"COPY-{book_id.upper()}-"
                f"{copy_number:03d}"
            )

            copy_data = {
                "copy_id": copy_id,
                "book_id": book_id,
                "copy_number": copy_number,
                "status": "Available",
                "condition": "Good",
                "created_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }

            copies_collection.document(
                copy_id
            ).set(copy_data)

            generated_copy_ids.append(copy_id)

        updated_copies = _get_book_copies(book_id)

        copy_summary = _calculate_copy_summary(
            updated_copies
        )

        main_book_status = "Available"

        if copy_summary["available"] == 0:
            main_book_status = "Unavailable"

        book_reference.update(
            {
                "total_copies": copy_summary["total"],
                "available_copies": (
                    copy_summary["available"]
                ),
                "status": main_book_status,
                "updated_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )

        flash(
            (
                f"{quantity} additional physical "
                "book copies were added successfully."
            ),
            "success",
        )

        return redirect(
            url_for(
                "book_catalogue.librarian_book_details",
                book_id=book_id,
            )
        )

    return render_template(
        "add_book_copies.html",
        book=book,
        copies=copies,
    )

# ============================================================
# SCRUM-704: DELETE BOOK RECORD
# ============================================================

@book_bp.route("/delete/<book_id>", methods=["GET"])
def delete_book(book_id):
    db.collection(COLLECTION_BOOKS).document(book_id).delete()

    flash(
        "Book record deleted successfully.",
        "success",
    )

    return redirect(
        url_for("book_catalogue.manage_books")
    )