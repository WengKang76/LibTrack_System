from flask import Flask, render_template

from modules.book_catalogue.routes import book_bp
from modules.student_catalogue.routes import student_catalogue_bp

app = Flask(__name__)
app.secret_key = "libtrack-secret-key"

app.register_blueprint(book_bp)
app.register_blueprint(student_catalogue_bp)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)