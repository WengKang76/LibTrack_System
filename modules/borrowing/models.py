from typing import TypedDict


class BorrowRequest(TypedDict):
    id: int
    student: str
    book: str
    status: str
