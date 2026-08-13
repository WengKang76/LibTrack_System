# Author: Tan Wei Khye

"""
Test cases for Scrum-1680 and Scrum-1681:
Display dashboard notifications for books that are due soon
or overdue.
"""

from modules.catalogue_reservation.routes import (
    get_due_date_notifications,
)


def test_no_notification_when_book_is_not_due_soon():
    """
    Given a student has a book due in more than 3 days

    ```
    When due-date notification checking is performed

    Then no notification should be returned
    """


borrowed_books = [
    {
        "book_title": "Clean Code",
        "remaining_days": 5,
    }
]

result = get_due_date_notifications(borrowed_books)

assert result == []


def test_overdue_book_notification():
    """
    Given a student has an overdue book

    ```
    When due-date notification checking is performed

    Then an overdue notification should be returned
    """


borrowed_books = [
    {
        "book_title": "Clean Code",
        "remaining_days": -1,
    }
]

result = get_due_date_notifications(borrowed_books)

assert len(result) == 1
assert result[0]["type"] == "overdue"
assert result[0]["count"] == 1
assert result[0]["books"] == ["Clean Code"]


def test_multiple_overdue_books_are_grouped():
    """
    Given a student has multiple overdue books

    ```
    When due-date notification checking is performed

    Then the overdue books should be grouped into one notification
    """


borrowed_books = [
    {
        "book_title": "Clean Code",
        "remaining_days": -1,
    },
    {
        "book_title": "Design Patterns",
        "remaining_days": -3,
    },
]

result = get_due_date_notifications(borrowed_books)

assert len(result) == 1
assert result[0]["type"] == "overdue"
assert result[0]["count"] == 2
assert result[0]["books"] == [
    "Clean Code",
    "Design Patterns",
]


def test_book_due_within_three_days():
    """
    Given a student has a book due within 3 days

    ```
    When due-date notification checking is performed

    Then a due-soon notification should be returned
    """


borrowed_books = [
    {
        "book_title": "Python Crash Course",
        "remaining_days": 3,
    }
]

result = get_due_date_notifications(borrowed_books)

assert len(result) == 1
assert result[0]["type"] == "due-soon"
assert result[0]["count"] == 1
assert result[0]["books"][0]["title"] == ("Python Crash Course")
assert result[0]["books"][0]["remaining_days"] == 3


def test_multiple_due_soon_books_are_grouped():
    """
    Given a student has multiple books due within 3 days

    ```
    When due-date notification checking is performed

    Then the books should be grouped into one notification
    """


borrowed_books = [
    {
        "book_title": "Python Crash Course",
        "remaining_days": 3,
    },
    {
        "book_title": "Java Programming",
        "remaining_days": 1,
    },
]

result = get_due_date_notifications(borrowed_books)

assert len(result) == 1
assert result[0]["type"] == "due-soon"
assert result[0]["count"] == 2


def test_overdue_and_due_soon_notifications_are_separated():
    """
    Given a student has an overdue book and a book due soon

    ```
    When due-date notification checking is performed

    Then separate notifications should be returned
    """


borrowed_books = [
    {
        "book_title": "Clean Code",
        "remaining_days": -1,
    },
    {
        "book_title": "Python Crash Course",
        "remaining_days": 2,
    },
]

result = get_due_date_notifications(borrowed_books)

assert len(result) == 2

notification_types = {notification["type"] for notification in result}

assert notification_types == {
    "overdue",
    "due-soon",
}


def test_book_without_remaining_days_is_ignored():
    """
    Given a borrowing record has no remaining-day information

    ```
    When due-date notification checking is performed

    Then no notification should be returned
    """


borrowed_books = [
    {
        "book_title": "Unknown Book",
        "remaining_days": None,
    }
]

result = get_due_date_notifications(borrowed_books)

assert result == []
