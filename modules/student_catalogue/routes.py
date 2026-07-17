from flask import Blueprint, render_template

from config.firebase_config import COLLECTION_BOOKS, db

student_catalogue_bp = Blueprint(
    "student_catalogue",
    __name__,
    url_prefix="/student/catalogue",
    template_folder=".",
)


def _is_visible_in_student_catalogue(book):
    visible = book.get("is_visible_to_students")
    if isinstance(visible, bool):
        return visible

    catalogue_status = str(book.get("catalogue_status", "Active")).lower()
    return catalogue_status not in {"inactive", "unavailable"}


def get_student_book_by_id(book_id):
    book_document = db.collection(COLLECTION_BOOKS).document(book_id).get()

    if not book_document.exists:
        return None

    book = book_document.to_dict() or {}
    if not _is_visible_in_student_catalogue(book):
        return None

    book["book_id"] = book_document.id
    return book


@student_catalogue_bp.route("/", methods=["GET"])
def view_catalogue():
    books = []

    for document in db.collection(COLLECTION_BOOKS).stream():
        book = document.to_dict() or {}
        book["book_id"] = document.id

        if _is_visible_in_student_catalogue(book):
            books.append(book)

    books.sort(key=lambda book: str(book.get("title", "")).lower())
    return render_template("catalogue.html", books=books)


@student_catalogue_bp.route(
    "/details/<book_id>",
    methods=["GET"],
)
def view_book_details(book_id):
    book = get_student_book_by_id(book_id)

    if book is None:
        return "Book record not found.", 404

    return render_template("book_details.html", book=book)
