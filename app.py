import importlib
import os

from flask import Flask, render_template

from modules.book_catalogue.routes import book_bp
from modules.catalogue_reservation.routes import catalogue_bp
from modules.penalty_transaction.routes import penalty_bp
from modules.student_catalogue.routes import student_catalogue_bp
from modules.user_management.routes import user_management_bp


app = Flask(__name__)

# Required by Flask flash messages and sessions.
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "libtrack-local-development-key",
)


# Register integrated modules exactly once.
app.register_blueprint(book_bp)
app.register_blueprint(student_catalogue_bp)
app.register_blueprint(user_management_bp)
app.register_blueprint(catalogue_bp)
app.register_blueprint(penalty_bp)


# Register the borrowing module when it is available.
OPTIONAL_BLUEPRINTS = (
    ("modules.borrowing_return.routes", "borrowing_bp"),
)

for module_name, blueprint_name in OPTIONAL_BLUEPRINTS:
    try:
        module = importlib.import_module(module_name)
        blueprint = getattr(module, blueprint_name)

        if blueprint.name not in app.blueprints:
            app.register_blueprint(blueprint)

    except (ModuleNotFoundError, AttributeError) as error:
        app.logger.warning(
            "Optional module %s was not registered: %s",
            module_name,
            error,
        )


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)