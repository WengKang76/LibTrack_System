from flask import Blueprint, render_template

from config.firebase_config import COLLECTION_BOOKS, db


student_catalogue_bp = Blueprint(
    "student_catalogue",
    __name__,
    url_prefix="/student/catalogue",
    template_folder=".",
)


def get_student_book_by_id(book_id):
    book_document = (
        db.collection(COLLECTION_BOOKS)
        .document(book_id)
        .get()
    )

    if not book_document.exists:
        return None

    book = book_document.to_dict() or {}
    book["book_id"] = book_document.id

    return book


@student_catalogue_bp.route("/", methods=["GET"])
def view_catalogue():
    book_documents = db.collection(COLLECTION_BOOKS).stream()

    books = []

    for document in book_documents:
        book = document.to_dict() or {}
        book["book_id"] = document.id
        books.append(book)

    books.sort(
        key=lambda book: book.get("title", "").lower()
    )

    return render_template(
        "catalogue.html",
        books=books,
    )


@student_catalogue_bp.route(
    "/details/<book_id>",
    methods=["GET"],
)
def view_book_details(book_id):
    book = get_student_book_by_id(book_id)

    if book is None:
        return "Book record not found.", 404

    return render_template(
        "book_details.html",
        book=book,
    )