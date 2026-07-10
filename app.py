from flask import Flask, render_template
from modules.borrowing.routes import borrowing_bp

app = Flask(__name__)

app.register_blueprint(borrowing_bp)


@app.route("/")
def home():
    return render_template("index.html")


# Add health check server endpoint for CI/CD purpose
@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
