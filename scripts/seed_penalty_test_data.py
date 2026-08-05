"""Seed Firebase with a dummy overdue borrow transaction and penalty record."""

import sys
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from config.firebase_config import (
    COLLECTION_BOOKS,
    COLLECTION_BORROW_TRANSACTIONS,
    COLLECTION_PENALTIES,
    COLLECTION_USERS,
    db,
)


def _create_dummy_overdue_case(index, today, now):
    overdue_days = 5 + index
    student_id = f"STU{999 - index}"
    user_id = f"USR{999 - index}"
    book_id = f"BKDUMMY{index:02d}"
    transaction_id = f"TXDUMMY{index:02d}"
    penalty_id = f"PNDUMMY{index:02d}"
    request_id = f"REQDUMMY{index:02d}"
    book_title = f"Dummy Overdue Book {index}"

    db.collection(COLLECTION_USERS).document(user_id).set(
        {
            "user_id": user_id,
            "student_id": student_id,
            "full_name": f"Dummy Student {index}",
            "email": f"dummy{index}@libtrack.test",
            "phone_number": f"012345678{index % 10}",
            "password_hash": "dummy-hash",
            "role": "Student",
            "account_status": "Active",
            "created_at": now,
            "updated_at": now,
            "is_dummy_account": True,
        }
    )

    db.collection(COLLECTION_BOOKS).document(book_id).set(
        {
            "book_id": book_id,
            "title": book_title,
            "author": "Demo Author",
            "category": "Demo",
            "status": "Available",
            "available_copies": 1,
            "total_copies": 1,
            "is_visible_to_students": True,
            "created_at": now,
            "updated_at": now,
        }
    )

    db.collection(COLLECTION_BORROW_TRANSACTIONS).document(transaction_id).set(
        {
            "request_id": request_id,
            "student_id": student_id,
            "book_id": book_id,
            "book_title": book_title,
            "borrow_date": (today - timedelta(days=overdue_days + 5)).isoformat(),
            "due_date": (today - timedelta(days=overdue_days)).isoformat(),
            "return_date": None,
            "status": "Borrowed",
            "renewal_status": "None",
            "show_renewal_message": False,
            "renewal_message": "",
            "created_at": now,
            "updated_at": now,
        }
    )

    db.collection(COLLECTION_PENALTIES).document(penalty_id).set(
        {
            "penalty_id": penalty_id,
            "student_id": student_id,
            "transaction_id": transaction_id,
            "book_title": book_title,
            "overdue_days": overdue_days,
            "penalty_amount": float(overdue_days),
            "status": "Outstanding",
            "created_at": now,
            "updated_at": now,
        }
    )

    return {
        "student_id": student_id,
        "book_id": book_id,
        "transaction_id": transaction_id,
        "penalty_id": penalty_id,
        "overdue_days": overdue_days,
    }


def seed_penalty_test_data(count=3):
    today = date.today()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    created_cases = []

    for index in range(1, count + 1):
        created_cases.append(_create_dummy_overdue_case(index, today, now))

    print("Seeded dummy overdue data into Firestore:")
    for case in created_cases:
        print(
            f"- {case['student_id']} | {case['book_id']} | "
            f"{case['transaction_id']} | {case['penalty_id']} | "
            f"{case['overdue_days']} overdue days"
        )


if __name__ == "__main__":
    seed_penalty_test_data(count=3)
