from functools import wraps

from flask import redirect, session


def login_required(view_function):
    """
    Allow only authenticated users to access the route.
    """

    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/auth/login")

        return view_function(*args, **kwargs)

    return wrapped_view


def roles_required(*allowed_roles):
    """
    Allow only users with one of the specified roles.
    """

    normalised_roles = {
        str(role).strip().lower()
        for role in allowed_roles
    }

    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            if not session.get("user_id"):
                return redirect("/auth/login")

            current_role = str(
                session.get("role", "")
            ).strip().lower()

            if current_role not in normalised_roles:
                return (
                    "Access denied. You do not have permission "
                    "to access this page.",
                    403,
                )

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator


def librarian_required(view_function):
    """
    Allow only authenticated librarians.
    """

    return roles_required("librarian")(
        view_function
    )


def student_required(view_function):
    """
    Allow only authenticated students.
    """

    return roles_required("student")(
        view_function
    )


def student_or_librarian_required(view_function):
    """
    Allow authenticated students and librarians.
    """

    return roles_required(
        "student",
        "librarian",
    )(view_function)