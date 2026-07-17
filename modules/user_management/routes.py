from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    url_for,
)

from config.firebase_config import (
    COLLECTION_USERS,
    db,
)


user_management_bp = Blueprint(
    "user_management",
    __name__,
    url_prefix="/users",
    template_folder=".",
)


def _current_timestamp():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def get_user_by_id(user_id):
    """
    Retrieve one user using the Firestore document ID.
    """
    user_document = (
        db.collection(COLLECTION_USERS)
        .document(user_id)
        .get()
    )

    if not user_document.exists:
        return None

    user = user_document.to_dict() or {}

    user["document_id"] = user_document.id
    user.setdefault(
        "user_id",
        user_document.id,
    )

    return user


# ============================================================
# SCRUM-511: VIEW ALL REGISTERED USERS
# ============================================================

@user_management_bp.route(
    "/",
    methods=["GET"],
)
def manage_users():
    user_documents = (
        db.collection(COLLECTION_USERS)
        .stream()
    )

    users = []

    for document in user_documents:
        user = document.to_dict() or {}

        role = str(
            user.get("role", "")
        ).strip().lower()

        # User Management displays only Student accounts.
        if role != "student":
            continue

        user["document_id"] = document.id

        user.setdefault(
            "user_id",
            document.id,
        )

        users.append(user)

    users.sort(
        key=lambda user: str(
            user.get("full_name", "")
        ).lower()
    )

    return render_template(
        "manage_users.html",
        users=users,
    )

# ============================================================
# SCRUM-512: VIEW SELECTED USER DETAILS
# ============================================================

@user_management_bp.route(
    "/details/<user_id>",
    methods=["GET"],
)
def user_details(user_id):
    user = get_user_by_id(user_id)

    if user is None:
        return "User record not found.", 404

    return render_template(
        "user_details.html",
        user=user,
    )


# ============================================================
# SCRUM-509: DEACTIVATE STUDENT ACCOUNT
# ============================================================

@user_management_bp.route(
    "/deactivate/<user_id>",
    methods=["POST"],
)
def deactivate_student(user_id):
    user = get_user_by_id(user_id)

    if user is None:
        return "User record not found.", 404

    user_role = str(
        user.get(
            "role",
            "",
        )
    ).strip().lower()

    if user_role != "student":
        return (
            "Only Student accounts can be deactivated.",
            400,
        )

    current_status = str(
        user.get(
            "account_status",
            "",
        )
    ).strip().lower()

    if current_status == "inactive":
        return (
            "This Student account is already inactive.",
            400,
        )

    current_time = _current_timestamp()

    (
        db.collection(COLLECTION_USERS)
        .document(user_id)
        .update(
            {
                "account_status": "Inactive",
                "deactivated_at": current_time,
                "updated_at": current_time,
            }
        )
    )

    flash(
        (
            f"{user.get('full_name', 'The Student')} "
            "account was deactivated successfully."
        ),
        "success",
    )

    return redirect(
        url_for(
            "user_management.user_details",
            user_id=user_id,
        )
    )

# ============================================================
# SCRUM-509: REACTIVATE STUDENT ACCOUNT
# ============================================================

@user_management_bp.route(
    "/reactivate/<user_id>",
    methods=["POST"],
)
def reactivate_student(user_id):
    user = get_user_by_id(user_id)

    if user is None:
        return "User record not found.", 404

    user_role = str(
        user.get(
            "role",
            "",
        )
    ).strip().lower()

    if user_role != "student":
        return (
            "Only Student accounts can be reactivated.",
            400,
        )

    current_status = str(
        user.get(
            "account_status",
            "",
        )
    ).strip().lower()

    if current_status == "active":
        return (
            "This Student account is already active.",
            400,
        )

    current_time = _current_timestamp()

    (
        db.collection(COLLECTION_USERS)
        .document(user_id)
        .update(
            {
                "account_status": "Active",
                "reactivated_at": current_time,
                "updated_at": current_time,
            }
        )
    )

    flash(
        (
            f"{user.get('full_name', 'The Student')} "
            "account was reactivated successfully."
        ),
        "success",
    )

    return redirect(
        url_for(
            "user_management.user_details",
            user_id=user_id,
        )
    )
