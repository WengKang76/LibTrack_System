from flask import Flask, render_template

from modules.book_catalogue.routes import book_bp
from modules.catalogue_reservation.routes import catalogue_bp
from modules.borrowing_return.routes import borrowing_bp
from modules.penalty_transaction.routes import penalty_bp

app = Flask(__name__)

app.register_blueprint(book_bp)
app.register_blueprint(catalogue_bp)
app.register_blueprint(borrowing_bp)
app.register_blueprint(penalty_bp)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)