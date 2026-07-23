import re
from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.security import generate_password_hash

from config.firebase_config import (
    COLLECTION_USERS,
    db,
)


authentication_bp = Blueprint(
    "authentication",
    __name__,
    url_prefix="/auth",
    template_folder=".",
)


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)

STUDENT_ID_PATTERN = re.compile(
    r"^[A-Za-z0-9-]{4,20}$"
)

PHONE_PATTERN = re.compile(
    r"^[0-9+\-\s]{7,20}$"
)


def _current_timestamp():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _normalise_email(email):
    return str(email).strip().lower()


def _validate_password(password):
    errors = []

    if len(password) < 8:
        errors.append(
            "Password must contain at least 8 characters."
        )

    if not re.search(r"[A-Z]", password):
        errors.append(
            "Password must contain at least one uppercase letter."
        )

    if not re.search(r"[a-z]", password):
        errors.append(
            "Password must contain at least one lowercase letter."
        )

    if not re.search(r"[0-9]", password):
        errors.append(
            "Password must contain at least one number."
        )

    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append(
            "Password must contain at least one special character."
        )

    if re.search(r"\s", password):
        errors.append(
            "Password must not contain spaces."
        )

    return errors


def _get_existing_users():
    return list(
        db.collection(
            COLLECTION_USERS
        ).stream()
    )


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
    normalised_student_id = (
        str(student_id)
        .strip()
        .upper()
    )

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

        if (
            existing_student_id
            == normalised_student_id
        ):
            return True

    return False


def _generate_next_user_id():
    highest_number = 0

    for document in _get_existing_users():
        user = document.to_dict() or {}

        user_id = str(
            user.get(
                "user_id",
                document.id,
            )
        ).strip().upper()

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
            "confirm_password": (
                "Password confirmation is required."
            ),
        }

        submitted_values = {
            **form_data,
            "password": password,
            "confirm_password": confirm_password,
        }

        for field_name, message in required_fields.items():
            if not submitted_values.get(field_name):
                errors[field_name] = message

        if (
            form_data["student_id"]
            and not STUDENT_ID_PATTERN.fullmatch(
                form_data["student_id"]
            )
        ):
            errors["student_id"] = (
                "Student ID must contain 4 to 20 "
                "letters, numbers, or hyphens."
            )

        if (
            form_data["full_name"]
            and len(form_data["full_name"]) > 100
        ):
            errors["full_name"] = (
                "Full name must not exceed 100 characters."
            )

        if (
            form_data["email"]
            and not EMAIL_PATTERN.fullmatch(
                form_data["email"]
            )
        ):
            errors["email"] = (
                "Enter a valid email address."
            )

        if (
            form_data["phone_number"]
            and not PHONE_PATTERN.fullmatch(
                form_data["phone_number"]
            )
        ):
            errors["phone_number"] = (
                "Enter a valid phone number."
            )

        if password:
            password_errors = _validate_password(
                password
            )

            if password_errors:
                errors["password"] = " ".join(
                    password_errors
                )

        if (
            password
            and confirm_password
            and password != confirm_password
        ):
            errors["confirm_password"] = (
                "Password and confirmation password "
                "do not match."
            )

        if (
            form_data["email"]
            and "email" not in errors
            and _email_exists(
                form_data["email"]
            )
        ):
            errors["email"] = (
                "An account already exists with "
                "this email address."
            )

        if (
            form_data["student_id"]
            and "student_id" not in errors
            and _student_id_exists(
                form_data["student_id"]
            )
        ):
            errors["student_id"] = (
                "An account already exists with "
                "this student ID."
            )

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
            "student_id": (
                form_data["student_id"].upper()
            ),
            "full_name": form_data["full_name"],
            "email": form_data["email"],
            "phone_number": (
                form_data["phone_number"]
            ),
            "password_hash": (
                generate_password_hash(
                    password
                )
            ),
            "role": "Student",
            "account_status": "Inactive",
            "created_at": current_time,
            "updated_at": current_time,
            "is_dummy_account": False,
        }

        (
            db.collection(
                COLLECTION_USERS
            )
            .document(user_id)
            .set(student_record)
        )

        flash(
            (
                "Registration submitted successfully. "
                "Your student account is waiting for "
                "librarian activation."
            ),
            "success",
        )

        return redirect(
            url_for(
                "authentication.register"
            )
        )

    return render_template(
        "register.html",
        form_data=form_data,
        errors=errors,
    )