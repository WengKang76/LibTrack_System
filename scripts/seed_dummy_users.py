import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from config.firebase_config import (  # noqa: E402
    COLLECTION_USERS,
    db,
)

DUMMY_USERS = [
    {
        "user_id": "USR001",
        "full_name": "Alicia Tan",
        "email": "alicia.tan@student.demo",
        "phone_number": "012-3456789",
        "role": "Student",
        "account_status": "Active",
    },
    {
        "user_id": "USR002",
        "full_name": "Daniel Lee",
        "email": "daniel.lee@student.demo",
        "phone_number": "013-4567890",
        "role": "Student",
        "account_status": "Active",
    },
    {
        "user_id": "USR003",
        "full_name": "Nur Aisyah",
        "email": "nur.aisyah@student.demo",
        "phone_number": "014-5678901",
        "role": "Student",
        "account_status": "Inactive",
    },
    {
        "user_id": "USR004",
        "full_name": "Marcus Lim",
        "email": "marcus.lim@student.demo",
        "phone_number": "016-6789012",
        "role": "Student",
        "account_status": "Active",
    },
    {
        "user_id": "USR005",
        "full_name": "Sarah Wong",
        "email": "sarah.wong@staff.demo",
        "phone_number": "017-7890123",
        "role": "Librarian",
        "account_status": "Active",
    },
]


def seed_dummy_users():
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    users_collection = db.collection(COLLECTION_USERS)

    for user in DUMMY_USERS:
        user_data = {
            **user,
            "created_at": current_time,
            "updated_at": current_time,
            "is_dummy_account": True,
        }

        users_collection.document(user["user_id"]).set(
            user_data,
            merge=True,
        )

        print(f"Seeded {user['user_id']}: " f"{user['full_name']}")

    print(f"\n{len(DUMMY_USERS)} dummy users " "were seeded successfully.")


if __name__ == "__main__":
    seed_dummy_users()
