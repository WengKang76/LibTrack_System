from flask import Flask, render_template

from modules.book_catalogue.routes import book_bp

app = Flask(__name__)
app.secret_key = "libtrack-secret-key"

app.register_blueprint(book_bp)


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)