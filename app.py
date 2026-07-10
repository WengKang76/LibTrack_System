import importlib
import os

from flask import Flask, render_template

from modules.catalogue_reservation.routes import catalogue_bp

app = Flask(__name__)

# flash() requires a secret key. Set SECRET_KEY in the environment for
# production; this fallback is only for local development.
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "libtrack-local-development-key"
)

# This branch already contains the Catalogue Browsing & Reservation module.
app.register_blueprint(catalogue_bp)

# These modules belong to other team members. The application will register
# them automatically after their branches are merged, but it can still run
# locally when they are not present yet.
OPTIONAL_BLUEPRINTS = (
    ("modules.book_catalogue.routes", "book_bp"),
    ("modules.borrowing_return.routes", "borrowing_bp"),
    ("modules.penalty_transaction.routes", "penalty_bp"),
)

for module_name, blueprint_name in OPTIONAL_BLUEPRINTS:
    try:
        module = importlib.import_module(module_name)
        blueprint = getattr(module, blueprint_name)
        app.register_blueprint(blueprint)
    except (ModuleNotFoundError, AttributeError) as error:
        app.logger.warning(
            "Optional module %s was not registered: %s",
            module_name,
            error
        )


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
