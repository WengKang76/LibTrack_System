import os

from flask import Flask, render_template

from modules.book_catalogue.routes import book_bp
from modules.borrowing.routes import borrowing_bp
from modules.catalogue_reservation.routes import catalogue_bp
from modules.penalty_transaction.routes import penalty_bp
from modules.student_catalogue.routes import student_catalogue_bp
from modules.user_management.routes import user_management_bp

app = Flask(__name__)

# Required for Flask sessions and flash messages.
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "libtrack-local-development-key",
)


# Register each integrated module exactly once.
app.register_blueprint(book_bp)
app.register_blueprint(student_catalogue_bp)
app.register_blueprint(user_management_bp)
app.register_blueprint(catalogue_bp)
app.register_blueprint(penalty_bp)
app.register_blueprint(borrowing_bp)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/")
def role_selection():
    return render_template("role_selection.html")


@app.route("/librarian")
def librarian_dashboard():
    return render_template("librarian_dashboard.html")


@app.route("/student")
def student_dashboard():
    return render_template("student_dashboard.html")


# Health-check endpoint for CI/CD and deployment checks.
@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000,
    )
