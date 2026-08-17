import re
import time
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from config.firebase_config import (
    COLLECTION_USERS,
    db,
)

from itsdangerous import (
    BadSignature,
    SignatureExpired,
    URLSafeTimedSerializer,
)

authentication_bp = Blueprint(
    "authentication",
    __name__,
    url_prefix="/auth",
    template_folder=".",
)


@authentication_bp.before_app_request
def check_session_expiration():
    """
    Automatically expire an authenticated session after
    the configured inactivity period.
    """

    if not session.get("user_id"):
        return None

    current_time = time.time()
    last_activity = session.get("last_activity")

    timeout_seconds = current_app.permanent_session_lifetime.total_seconds()

    if last_activity is not None:
        try:
            inactivity_period = current_time - float(last_activity)
        except (TypeError, ValueError):
            inactivity_period = timeout_seconds + 1

        if inactivity_period > timeout_seconds:
            session.clear()

            flash(
                ("Your session has expired due to inactivity. " "Please log in again."),
                "warning",
            )

            return redirect(url_for("authentication.login"))

    session["last_activity"] = current_time
    session.modified = True

    return None


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

STUDENT_ID_PATTERN = re.compile(r"^[0-9]{7}$")

PHONE_PATTERN = re.compile(r"^[0-9+\-\s]{7,20}$")


def _current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalise_email(email):
    return str(email).strip().lower()


def _find_user_by_email(email):
    normalised_email = _normalise_email(email)

    user_documents = db.collection(COLLECTION_USERS).stream()

    for document in user_documents:
        user = document.to_dict() or {}

        existing_email = _normalise_email(user.get("email", ""))

        if existing_email == normalised_email:
            user["document_id"] = document.id
            user.setdefault(
                "user_id",
                document.id,
            )

            return user

    return None


def _get_password_reset_serializer():
    """
    Create a signed serializer using the Flask secret key.
    """

    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt="libtrack-password-reset",
    )


def _generate_password_reset_token(user):
    """
    Generate a signed reset token for one user.
    """

    reset_version = int(
        user.get(
            "password_reset_version",
            0,
        )
    )

    token_data = {
        "email": _normalise_email(user.get("email", "")),
        "version": reset_version,
    }

    return _get_password_reset_serializer().dumps(token_data)


def _load_password_reset_token(token):
    """
    Validate and decode a reset token.
    """

    maximum_age = int(
        current_app.config.get(
            "PASSWORD_RESET_TOKEN_MAX_AGE",
            900,
        )
    )

    try:
        token_data = _get_password_reset_serializer().loads(
            token,
            max_age=maximum_age,
        )
    except (
        BadSignature,
        SignatureExpired,
        TypeError,
        ValueError,
    ):
        return None

    if not isinstance(token_data, dict):
        return None

    email = _normalise_email(token_data.get("email", ""))

    try:
        reset_version = int(
            token_data.get(
                "version",
                -1,
            )
        )
    except (TypeError, ValueError):
        return None

    if not email or reset_version < 0:
        return None

    return {
        "email": email,
        "version": reset_version,
    }


def _validate_password(password):
    errors = []

    if len(password) < 8:
        errors.append("Password must contain at least 8 characters.")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")

    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")

    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number.")

    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Password must contain at least one special character.")

    if re.search(r"\s", password):
        errors.append("Password must not contain spaces.")

    return errors


def _get_existing_users():
    return list(db.collection(COLLECTION_USERS).stream())


def _email_exists(email):
    normalised_email = _normalise_email(email)

    for document in _get_existing_users():
        user = document.to_dict() or {}

        existing_email = _normalise_email(
            user.get(
                "email",
                "",
            )
        )

        if existing_email == normalised_email:
            return True

    return False


def _student_id_exists(student_id):
    normalised_student_id = str(student_id).strip().upper()

    for document in _get_existing_users():
        user = document.to_dict() or {}

        existing_student_id = (
            str(
                user.get(
                    "student_id",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if existing_student_id == normalised_student_id:
            return True

    return False


def _generate_next_user_id():
    highest_number = 0

    for document in _get_existing_users():
        user = document.to_dict() or {}

        user_id = (
            str(
                user.get(
                    "user_id",
                    document.id,
                )
            )
            .strip()
            .upper()
        )

        match = re.fullmatch(
            r"USR(\d+)",
            user_id,
        )

        if match:
            highest_number = max(
                highest_number,
                int(match.group(1)),
            )

    return f"USR{highest_number + 1:03d}"


@authentication_bp.route(
    "/register",
    methods=["GET", "POST"],
)
def register():
    form_data = {
        "student_id": "",
        "full_name": "",
        "email": "",
        "phone_number": "",
    }

    errors = {}

    if request.method == "POST":
        form_data = {
            "student_id": request.form.get(
                "student_id",
                "",
            ).strip(),
            "full_name": request.form.get(
                "full_name",
                "",
            ).strip(),
            "email": _normalise_email(
                request.form.get(
                    "email",
                    "",
                )
            ),
            "phone_number": request.form.get(
                "phone_number",
                "",
            ).strip(),
        }

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        required_fields = {
            "student_id": "Student ID is required.",
            "full_name": "Full name is required.",
            "email": "Email address is required.",
            "phone_number": "Phone number is required.",
            "password": "Password is required.",
            "confirm_password": ("Password confirmation is required."),
        }

        submitted_values = {
            **form_data,
            "password": password,
            "confirm_password": confirm_password,
        }

        for field_name, message in required_fields.items():
            if not submitted_values.get(field_name):
                errors[field_name] = message

        if form_data["student_id"] and not STUDENT_ID_PATTERN.fullmatch(
            form_data["student_id"]
        ):
            errors["student_id"] = (
                "Student ID must contain exactly 7 digits."
            )

        if form_data["full_name"] and len(form_data["full_name"]) > 100:
            errors["full_name"] = "Full name must not exceed 100 characters."

        if form_data["email"] and not EMAIL_PATTERN.fullmatch(form_data["email"]):
            errors["email"] = "Enter a valid email address."

        if form_data["phone_number"] and not PHONE_PATTERN.fullmatch(
            form_data["phone_number"]
        ):
            errors["phone_number"] = "Enter a valid phone number."

        if password:
            password_errors = _validate_password(password)

            if password_errors:
                errors["password"] = " ".join(password_errors)

        if password and confirm_password and password != confirm_password:
            errors["confirm_password"] = (
                "Password and confirmation password " "do not match."
            )

        if (
            form_data["email"]
            and "email" not in errors
            and _email_exists(form_data["email"])
        ):
            errors["email"] = "An account already exists with " "this email address."

        if (
            form_data["student_id"]
            and "student_id" not in errors
            and _student_id_exists(form_data["student_id"])
        ):
            errors["student_id"] = "An account already exists with " "this student ID."

        if errors:
            return (
                render_template(
                    "register.html",
                    form_data=form_data,
                    errors=errors,
                ),
                400,
            )

        user_id = _generate_next_user_id()
        current_time = _current_timestamp()

        student_record = {
            "user_id": user_id,
            "student_id": (form_data["student_id"].upper()),
            "full_name": form_data["full_name"],
            "email": form_data["email"],
            "phone_number": (form_data["phone_number"]),
            "password_hash": (generate_password_hash(password)),
            "role": "Student",
            "account_status": "Inactive",
            "created_at": current_time,
            "updated_at": current_time,
            "is_dummy_account": False,
        }

        (db.collection(COLLECTION_USERS).document(user_id).set(student_record))

        flash(
            (
                "Registration submitted successfully. "
                "Your student account is waiting for "
                "librarian activation."
            ),
            "success",
        )

        return redirect(url_for("authentication.register"))

    return render_template(
        "register.html",
        form_data=form_data,
        errors=errors,
    )


@authentication_bp.route(
    "/login",
    methods=["GET", "POST"],
)
def login():
    form_data = {
        "email": "",
    }

    error_message = None

    if request.method == "POST":
        email = _normalise_email(
            request.form.get(
                "email",
                "",
            )
        )

        password = request.form.get(
            "password",
            "",
        )

        form_data["email"] = email

        if not email or not password:
            error_message = "Email and password are required."

            return (
                render_template(
                    "login.html",
                    form_data=form_data,
                    error_message=error_message,
                ),
                400,
            )

        user = _find_user_by_email(email)

        password_is_valid = False

        if user:
            stored_password_hash = str(
                user.get(
                    "password_hash",
                    "",
                )
            )

            if stored_password_hash:
                try:
                    password_is_valid = check_password_hash(
                        stored_password_hash,
                        password,
                    )
                except (TypeError, ValueError):
                    password_is_valid = False

        if not user or not password_is_valid:
            error_message = "Invalid email or password."

            return (
                render_template(
                    "login.html",
                    form_data=form_data,
                    error_message=error_message,
                ),
                401,
            )

        account_status = (
            str(
                user.get(
                    "account_status",
                    "Inactive",
                )
            )
            .strip()
            .lower()
        )

        if account_status != "active":
            error_message = (
                "Your account is currently inactive. " "Please contact a librarian."
            )

            return (
                render_template(
                    "login.html",
                    form_data=form_data,
                    error_message=error_message,
                ),
                403,
            )

        user_role = (
            str(
                user.get(
                    "role",
                    "",
                )
            )
            .strip()
            .lower()
        )

        session.clear()
        session.permanent = True
        session["last_activity"] = time.time()

        session["user_id"] = user.get(
            "user_id",
            user.get("document_id"),
        )

        session["full_name"] = user.get(
            "full_name",
            "",
        )

        session["email"] = user.get(
            "email",
            "",
        )

        session["student_id"] = (
            user.get("student_id")
            or user.get("user_id")
            or user.get("document_id")
            or ""
        )

        session["role"] = user_role

        flash(
            (f"Welcome, " f"{user.get('full_name', 'User')}."),
            "success",
        )

        if user_role == "librarian":
            return redirect("/librarian")

        return redirect("/")

    return render_template(
        "login.html",
        form_data=form_data,
        error_message=error_message,
    )


@authentication_bp.route(
    "/logout",
    methods=["POST"],
)
def logout():
    session.clear()

    flash(
        "You have logged out successfully.",
        "success",
    )

    return redirect("/")


@authentication_bp.route(
    "/forgot-password",
    methods=["GET", "POST"],
)
def forgot_password():
    # Must be created before every possible return path.
    development_reset_token = None

    form_data = {
        "email": "",
    }

    error_message = None
    success_message = None

    if request.method == "POST":
        email = _normalise_email(
            request.form.get(
                "email",
                "",
            )
        )

        form_data["email"] = email

        if not email:
            error_message = "Email address is required."

            return (
                render_template(
                    "forgot_password.html",
                    form_data=form_data,
                    error_message=error_message,
                    success_message=None,
                    development_reset_token=None,
                ),
                400,
            )

        if not EMAIL_PATTERN.fullmatch(email):
            error_message = "Enter a valid email address."

            return (
                render_template(
                    "forgot_password.html",
                    form_data=form_data,
                    error_message=error_message,
                    success_message=None,
                    development_reset_token=None,
                ),
                400,
            )

        user = _find_user_by_email(email)

        if user:
            token = _generate_password_reset_token(user)

            reset_url = url_for(
                "authentication.reset_password",
                token=token,
                _external=True,
            )

            current_app.logger.info(
                "Password reset link for %s: %s",
                email,
                reset_url,
            )

            # Local demonstration only.
            if current_app.config.get(
                "SHOW_PASSWORD_RESET_LINK",
                False,
            ):
                development_reset_token = token

        # Always use the same message to avoid
        # revealing whether the email exists.
        success_message = (
            "If an account exists for this email address, "
            "password reset instructions have been generated."
        )

    return render_template(
        "forgot_password.html",
        form_data=form_data,
        error_message=error_message,
        success_message=success_message,
        development_reset_token=development_reset_token,
    )


@authentication_bp.route(
    "/reset-password/<token>",
    methods=["GET", "POST"],
)
def reset_password(token):
    token_data = _load_password_reset_token(token)

    if token_data is None:
        return (
            render_template(
                "reset_password.html",
                token_valid=False,
                errors={},
            ),
            400,
        )

    user = _find_user_by_email(token_data["email"])

    if not user:
        return (
            render_template(
                "reset_password.html",
                token_valid=False,
                errors={},
            ),
            400,
        )

    current_reset_version = int(
        user.get(
            "password_reset_version",
            0,
        )
    )

    if current_reset_version != token_data["version"]:
        return (
            render_template(
                "reset_password.html",
                token_valid=False,
                errors={},
            ),
            400,
        )

    errors = {}

    if request.method == "POST":
        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not password:
            errors["password"] = "New password is required."
        else:
            password_errors = _validate_password(password)

            if password_errors:
                errors["password"] = " ".join(password_errors)

        if not confirm_password:
            errors["confirm_password"] = "Password confirmation is required."
        elif password and password != confirm_password:
            errors["confirm_password"] = (
                "Password and confirmation password " "do not match."
            )

        stored_password_hash = str(
            user.get(
                "password_hash",
                "",
            )
        )

        if (
            password
            and stored_password_hash
            and check_password_hash(
                stored_password_hash,
                password,
            )
        ):
            errors["password"] = (
                "The new password must be different " "from the current password."
            )

        if errors:
            return (
                render_template(
                    "reset_password.html",
                    token_valid=True,
                    errors=errors,
                ),
                400,
            )

        document_id = user.get(
            "document_id",
            user.get("user_id"),
        )

        (
            db.collection(COLLECTION_USERS)
            .document(document_id)
            .update(
                {
                    "password_hash": (generate_password_hash(password)),
                    "password_reset_version": (current_reset_version + 1),
                    "password_reset_at": (_current_timestamp()),
                    "updated_at": (_current_timestamp()),
                }
            )
        )

        session.clear()

        flash(
            (
                "Your password was reset successfully. "
                "You can now log in using your new password."
            ),
            "success",
        )

        return redirect(url_for("authentication.login"))

    return render_template(
        "reset_password.html",
        token_valid=True,
        errors=errors,
    )
