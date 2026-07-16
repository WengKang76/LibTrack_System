import os
import firebase_admin
from firebase_admin import credentials, firestore

_current_dir = os.path.dirname(os.path.abspath(__file__))
_key_path = os.path.join(_current_dir, "serviceAccountKey.json")


def init_firebase():
    if not firebase_admin._apps:
        if not os.path.exists(_key_path):
            raise FileNotFoundError(
                "serviceAccountKey.json not found in config folder."
            )

        cred = credentials.Certificate(_key_path)
        firebase_admin.initialize_app(cred)

    return firestore.client()


db = init_firebase()

COLLECTION_BOOKS = "books"
COLLECTION_USERS = "users"
COLLECTION_BORROW_REQUESTS = "borrow_requests"
COLLECTION_BORROW_TRANSACTIONS = "borrow_transactions"
COLLECTION_PENALTIES = "penalties"
COLLECTION_RESERVATIONS = "reservations"
