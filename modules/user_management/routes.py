from datetime import datetime

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from config.firebase_config import (
    COLLECTION_USERS,
    db,
)

from modules.authentication.decorators import (
    librarian_required,
)


user_management_bp = Blueprint(
    "user_management",
    __name__,
    url_prefix="/users",
    template_folder=".",
)


VALID_ACCOUNT_STATUS_FILTERS = {
    "all",
    "active",
    "inactive",
}

VALID_STUDENT_SORT_OPTIONS = {
    "name_asc",
    "name_desc",
    "student_id_asc",
    "student_id_desc",
    "registration_newest",
    "registration_oldest",
    "status_active_first",
    "status_inactive_first",
}


def _current_timestamp():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _normalise_text(value):
    return str(
        value or ""
    ).strip().casefold()


def _student_identifier(user):
    return str(
        user.get("student_id")
        or user.get("user_id")
        or user.get("document_id")
        or ""
    ).strip()


def _student_matches_search(
    user,
    search_query,
):
    normalised_query = _normalise_text(
        search_query
    )

    if not normalised_query:
        return True

    searchable_values = (
        user.get("full_name", ""),
        _student_identifier(user),
        user.get("email", ""),
    )

    return any(
        normalised_query
        in _normalise_text(value)
        for value in searchable_values
    )


def _parse_registration_timestamp(value):
    if isinstance(value, datetime):
        try:
            return value.timestamp()
        except (
            OverflowError,
            OSError,
            ValueError,
        ):
            return None

    text_value = str(
        value or ""
    ).strip()

    if not text_value:
        return None

    supported_formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    )

    for date_format in supported_formats:
        try:
            parsed_value = datetime.strptime(
                text_value,
                date_format,
            )

            return parsed_value.timestamp()
        except ValueError:
            continue

    return None


def _sort_students(
    users,
    sort_option,
):
    def name_key(user):
        return (
            _normalise_text(
                user.get(
                    "full_name",
                    "",
                )
            ),
            _normalise_text(
                _student_identifier(user)
            ),
        )

    def student_id_key(user):
        return (
            _normalise_text(
                _student_identifier(user)
            ),
            _normalise_text(
                user.get(
                    "full_name",
                    "",
                )
            ),
        )

    def registration_key(
        user,
        newest=False,
    ):
        timestamp = (
            _parse_registration_timestamp(
                user.get("created_at")
            )
        )

        is_missing = timestamp is None

        safe_timestamp = (
            timestamp
            if timestamp is not None
            else 0.0
        )

        return (
            is_missing,
            (
                -safe_timestamp
                if newest
                else safe_timestamp
            ),
            _normalise_text(
                user.get(
                    "full_name",
                    "",
                )
            ),
        )

    def status_key(
        user,
        inactive_first=False,
    ):
        status = _normalise_text(
            user.get(
                "account_status",
                "inactive",
            )
        )

        if inactive_first:
            status_rank = {
                "inactive": 0,
                "active": 1,
            }.get(
                status,
                2,
            )
        else:
            status_rank = {
                "active": 0,
                "inactive": 1,
            }.get(
                status,
                2,
            )

        return (
            status_rank,
            _normalise_text(
                user.get(
                    "full_name",
                    "",
                )
            ),
        )

    if sort_option == "name_desc":
        users.sort(
            key=name_key,
            reverse=True,
        )

    elif sort_option == "student_id_asc":
        users.sort(
            key=student_id_key,
        )

    elif sort_option == "student_id_desc":
        users.sort(
            key=student_id_key,
            reverse=True,
        )

    elif sort_option == "registration_newest":
        users.sort(
            key=lambda user: registration_key(
                user,
                newest=True,
            )
        )

    elif sort_option == "registration_oldest":
        users.sort(
            key=registration_key,
        )

    elif sort_option == "status_active_first":
        users.sort(
            key=status_key,
        )

    elif sort_option == "status_inactive_first":
        users.sort(
            key=lambda user: status_key(
                user,
                inactive_first=True,
            )
        )

    else:
        users.sort(
            key=name_key,
        )

    return users


def get_user_by_id(user_id):
    """
    Retrieve one user using the Firestore document ID.
    """

    user_document = (
        db.collection(
            COLLECTION_USERS
        )
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
# SCRUM-511, SCRUM-1519, SCRUM-1520, SCRUM-1521
# VIEW, SEARCH, FILTER AND SORT STUDENT ACCOUNTS
# ============================================================

@user_management_bp.route(
    "/",
    methods=["GET"],
)
@librarian_required
def manage_users():
    search_query = request.args.get(
        "q",
        "",
    ).strip()

    status_filter = _normalise_text(
        request.args.get(
            "status",
            "all",
        )
    )

    if (
        status_filter
        not in VALID_ACCOUNT_STATUS_FILTERS
    ):
        status_filter = "all"

    sort_option = _normalise_text(
        request.args.get(
            "sort",
            "name_asc",
        )
    )

    if (
        sort_option
        not in VALID_STUDENT_SORT_OPTIONS
    ):
        sort_option = "name_asc"

    user_documents = (
        db.collection(
            COLLECTION_USERS
        ).stream()
    )

    users = []

    for document in user_documents:
        user = document.to_dict() or {}

        role = _normalise_text(
            user.get(
                "role",
                "",
            )
        )

        if role != "student":
            continue

        user["document_id"] = document.id

        user.setdefault(
            "user_id",
            document.id,
        )

        if not _student_matches_search(
            user,
            search_query,
        ):
            continue

        account_status = _normalise_text(
            user.get(
                "account_status",
                "inactive",
            )
        )

        if (
            status_filter != "all"
            and account_status
            != status_filter
        ):
            continue

        users.append(user)

    _sort_students(
        users,
        sort_option,
    )

    has_active_criteria = bool(
        search_query
        or status_filter != "all"
        or sort_option != "name_asc"
    )

    return render_template(
        "manage_users.html",
        users=users,
        search_query=search_query,
        status_filter=status_filter,
        sort_option=sort_option,
        result_count=len(users),
        has_active_criteria=(
            has_active_criteria
        ),
    )


# ============================================================
# SCRUM-512: VIEW SELECTED USER DETAILS
# ============================================================

@user_management_bp.route(
    "/details/<user_id>",
    methods=["GET"],
)
@librarian_required
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
@librarian_required
def deactivate_student(user_id):
    user = get_user_by_id(user_id)

    if user is None:
        return "User record not found.", 404

    user_role = _normalise_text(
        user.get(
            "role",
            "",
        )
    )

    if user_role != "student":
        return (
            "Only Student accounts can be deactivated.",
            400,
        )

    current_status = _normalise_text(
        user.get(
            "account_status",
            "",
        )
    )

    if current_status == "inactive":
        return (
            "This Student account is already inactive.",
            400,
        )

    current_time = _current_timestamp()

    (
        db.collection(
            COLLECTION_USERS
        )
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
@librarian_required
def reactivate_student(user_id):
    user = get_user_by_id(user_id)

    if user is None:
        return "User record not found.", 404

    user_role = _normalise_text(
        user.get(
            "role",
            "",
        )
    )

    if user_role != "student":
        return (
            "Only Student accounts can be reactivated.",
            400,
        )

    current_status = _normalise_text(
        user.get(
            "account_status",
            "",
        )
    )

    if current_status == "active":
        return (
            "This Student account is already active.",
            400,
        )

    current_time = _current_timestamp()

    (
        db.collection(
            COLLECTION_USERS
        )
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