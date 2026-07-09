from flask import Blueprint, render_template, request, redirect, url_for, flash
from config.firebase_config import db, COLLECTION_BOOKS

book_bp = Blueprint("book_catalogue", __name__, url_prefix="/books")


@book_bp.route("/add", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        isbn = request.form.get("isbn")
        category = request.form.get("category")
        total_copies = request.form.get("total_copies")

        if not title or not author or not isbn or not category or not total_copies:
            flash("Please fill in all required fields.")
            return redirect(url_for("book_catalogue.add_book"))

        book_data = {
            "title": title,
            "author": author,
            "isbn": isbn,
            "category": category,
            "total_copies": int(total_copies),
            "available_copies": int(total_copies),
            "status": "Available"
        }

        db.collection(COLLECTION_BOOKS).add(book_data)

        flash("Book record added successfully.")
        return redirect(url_for("book_catalogue.add_book"))

    return render_template("book_catalogue/add_book.html")