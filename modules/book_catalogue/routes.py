from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from config.firebase_config import COLLECTION_BOOKS, db


book_bp = Blueprint(
    "book_catalogue",
    __name__,
    url_prefix="/books",
    template_folder=".",
)


def _isbn_already_exists(isbn, exclude_book_id=None):
    """
    Check whether an ISBN is already used by another book.

    exclude_book_id is used during editing so that the current book
    can retain its existing ISBN.
    """
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
            "total_copies": total_copies,
            "available_copies": total_copies,
            "status": "Available",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        db.collection(COLLECTION_BOOKS).add(book_data)

        flash("Book record added successfully.", "success")

        return redirect(url_for("book_catalogue.add_book"))

    return render_template("add_book.html", form_data=form_data)

# ============================================================
# BOOK MANAGEMENT PAGE
# ============================================================

@book_bp.route("/", methods=["GET"])
def manage_books():
    """Display all books with a link to edit each record."""
    book_documents = db.collection(COLLECTION_BOOKS).stream()

    books = []

    for document in book_documents:
        book = document.to_dict() or {}
        book["book_id"] = document.id
        books.append(book)

    # Sort books alphabetically by title
    books.sort(
        key=lambda book: book.get("title", "").lower()
    )

    return render_template(
        "manage_books.html",
        books=books,
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