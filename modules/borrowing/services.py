from modules.borrowing.repository import (
    find_request,
    get_pending_requests,
)


def get_all_pending_requests():
    return get_pending_requests()


def approve_borrow_request(request_id: int) -> bool:
    request = find_request(request_id)

    if request is None:
        return False

    if request["status"] != "Pending":
        return False

    request["status"] = "Approved"

    return True
