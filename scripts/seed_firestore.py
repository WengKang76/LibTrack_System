"""
This file is used to seed the Firestore databse with initial data for testing and development purposes.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config.firebase_config import db

from datetime import date, timedelta


# ==========================
# Users
# ==========================


def seed_users():

    users = {}

    # Students
    for i in range(1, 9):

        user_id = f"USR{i:03}"

        users[user_id] = {
            "full_name": f"Student {i}",
            "email": f"student{i}@tarumt.edu.my",
            "role": "student",
        }

    # Librarians
    users["LIB001"] = {
        "full_name": "Library Admin",
        "email": "admin@tarumt.edu.my",
        "role": "librarian",
    }

    users["LIB002"] = {
        "full_name": "Library Staff",
        "email": "staff@tarumt.edu.my",
        "role": "librarian",
    }

    for user_id, data in users.items():

        db.collection("users").document(user_id).set(data)


# ==========================
# Books
# ==========================


def seed_books():

    books = [
        ("Database System Concepts", "Silberschatz"),
        ("Software Engineering", "Ian Sommerville"),
        ("Clean Code", "Robert Martin"),
        ("Computer Networks", "Andrew Tanenbaum"),
        ("Operating System Concepts", "Silberschatz"),
        ("Artificial Intelligence", "Stuart Russell"),
        ("Data Structures and Algorithms", "Mark Allen Weiss"),
        ("Web Development Fundamentals", "Jon Duckett"),
        ("Introduction to Java Programming", "Y. Daniel Liang"),
        ("Computer Security", "William Stallings"),
    ]

    for index, (title, author) in enumerate(books, start=1):

        book_id = f"BOOK{index:03}"

        db.collection("books").document(book_id).set(
            {
                "title": title,
                "author": author,
                "available_copies": 3,
                "total_copies": 5,
            }
        )


# ==========================
# Borrow Requests
# ==========================


def seed_borrow_requests():

    statuses = [
        "Pending",
        "Approved",
        "Rejected",
    ]

    for i in range(1, 21):

        request_id = f"REQ{i:03}"

        student_id = f"USR{((i - 1) % 8) + 1:03}"

        book_id = f"BOOK{((i - 1) % 10) + 1:03}"

        db.collection("borrow_requests").document(request_id).set(
            {
                "book_id": book_id,
                "student_id": student_id,
                "borrowing_period": 14,
                "request_date": str(date.today()),
                "status": statuses[i % len(statuses)],
            }
        )


# ==========================
# Borrow Transactions
# ==========================


def seed_borrow_transactions():

    statuses = [
        "Borrowed",
        "Return Pending",
        "Returned",
        "Closed",
    ]

    for i in range(1, 21):

        transaction_id = f"TRAN{i:03}"

        request_id = f"REQ{i:03}"

        student_id = f"USR{((i - 1) % 8) + 1:03}"

        book_id = f"BOOK{((i - 1) % 10) + 1:03}"

        borrow_date = date.today() - timedelta(days=i)

        due_date = borrow_date + timedelta(days=14)

        status = statuses[i % len(statuses)]

        return_date = None

        if status in ["Returned", "Closed"]:

            return_date = str(borrow_date + timedelta(days=10))

        db.collection("borrow_transactions").document(transaction_id).set(
            {
                "request_id": request_id,
                "student_id": student_id,
                "book_id": book_id,
                "borrow_date": str(borrow_date),
                "due_date": str(due_date),
                "return_date": return_date,
                "status": status,
                "renewal_status": "None",
                "show_renewal_message": False,
                "renewal_message": "",
            }
        )


# ==========================
# Reservations
# ==========================


def seed_reservations():

    for i in range(1, 11):

        reservation_id = f"RES{i:03}"

        db.collection("reservations").document(reservation_id).set(
            {
                "book_id": f"BOOK{i:03}",
                "student_id": (f"USR{((i - 1) % 8) + 1:03}"),
                "status": "Pending",
            }
        )


# ==========================
# Run Seeder
# ==========================

if __name__ == "__main__":

    print("Seeding users...")
    seed_users()

    print("Seeding books...")
    seed_books()

    print("Seeding borrow requests...")
    seed_borrow_requests()

    print("Seeding borrow transactions...")
    seed_borrow_transactions()

    print("Seeding reservations...")
    seed_reservations()

    print("\nFirestore seed completed successfully!")
