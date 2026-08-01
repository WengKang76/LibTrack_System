import sys
from datetime import datetime
from pathlib import Path

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.firebase_config import (
    COLLECTION_USERS,
    db,
)

DOCUMENT_ID = "LIB001"
EMAIL = "admin@tarumt.edu.my"
PASSWORD = "Librarian@123"

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

librarian_record = {
    "user_id": DOCUMENT_ID,
    "full_name": "Library Admin",
    "email": EMAIL,
    "phone_number": "0123456789",
    "role": "Librarian",
    "account_status": "Active",
    "password_hash": generate_password_hash(PASSWORD),
    "created_at": current_time,
    "updated_at": current_time,
    "is_dummy_account": False,
}

document_reference = db.collection(COLLECTION_USERS).document(DOCUMENT_ID)

document_reference.set(
    librarian_record,
    merge=True,
)

saved_record = document_reference.get().to_dict() or {}

password_verified = check_password_hash(
    saved_record.get("password_hash", ""),
    PASSWORD,
)

print("")
print("Firebase project:", getattr(db, "project", "Unknown"))
print("Document ID:", DOCUMENT_ID)
print("Email:", saved_record.get("email"))
print("Role:", saved_record.get("role"))
print(
    "Account status:",
    saved_record.get("account_status"),
)
print(
    "Password verified:",
    password_verified,
)
