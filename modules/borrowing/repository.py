from typing import TypedDict


class BorrowRequest(TypedDict):
    id: int
    student: str
    book: str
    status: str


borrow_requests: list[BorrowRequest] = [
    {
        "id": 1,
        "student": "Alice",
        "book": "Database System Concepts",
        "status": "Pending",
    },
    {
        "id": 2,
        "student": "John",
        "book": "Software Engineering",
        "status": "Pending",
    },
]


def get_pending_requests() -> list[BorrowRequest]:
    return [request for request in borrow_requests if request["status"] == "Pending"]


def find_request(request_id: int) -> BorrowRequest | None:
    for request in borrow_requests:
        if request["id"] == request_id:
            return request

    return None
