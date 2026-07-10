from datetime import date, timedelta

import modules.penalty_transaction.routes as penalty_routes


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeDocumentRef:
    def __init__(self, records, doc_id):
        self.records = records
        self.doc_id = doc_id

    def update(self, update_data):
        self.records[self.doc_id].update(update_data)


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def stream(self):
        return [
            FakeDoc(doc_id, data)
            for doc_id, data in self.records.items()
        ]

    def document(self, doc_id):
        return FakeDocumentRef(self.records, doc_id)


class FakeDB:
    def __init__(self):
        self.borrow_transactions = {}

    def collection(self, collection_name):
        if collection_name == "borrow_transactions":
            return FakeCollection(self.borrow_transactions)

        return FakeCollection({})

    def insert_dummy_borrow_transaction(self, transaction_id, data):
        self.borrow_transactions[transaction_id] = data


def create_dummy_test_database():
    fake_db = FakeDB()

    yesterday = date.today() - timedelta(days=1)
    future_day = date.today() + timedelta(days=7)

    # Dummy Data 1: This book is overdue
    fake_db.insert_dummy_borrow_transaction("T001", {
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "borrow_date": "2026-07-01",
        "due_date": yesterday.strftime("%Y-%m-%d"),
        "status": "Borrowed"
    })

    # Dummy Data 2: This book is not overdue because due date is future
    fake_db.insert_dummy_borrow_transaction("T002", {
        "student_id": "S002",
        "book_id": "B002",
        "book_title": "Database System",
        "borrow_date": "2026-07-01",
        "due_date": future_day.strftime("%Y-%m-%d"),
        "status": "Borrowed"
    })

    # Dummy Data 3: This book is overdue by date but already returned
    fake_db.insert_dummy_borrow_transaction("T003", {
        "student_id": "S003",
        "book_id": "B003",
        "book_title": "Software Engineering",
        "borrow_date": "2026-07-01",
        "due_date": yesterday.strftime("%Y-%m-%d"),
        "status": "Returned"
    })

    return fake_db


def test_scrum_666_identify_overdue_books(monkeypatch):
    fake_db = create_dummy_test_database()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    overdue_books = penalty_routes.get_overdue_books()

    assert len(overdue_books) == 1
    assert overdue_books[0]["student_id"] == "S001"
    assert overdue_books[0]["book_id"] == "B001"
    assert overdue_books[0]["book_title"] == "Python Programming"


def test_scrum_666_not_include_future_due_date(monkeypatch):
    fake_db = create_dummy_test_database()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    overdue_books = penalty_routes.get_overdue_books()

    book_titles = [book["book_title"] for book in overdue_books]

    assert "Database System" not in book_titles


def test_scrum_666_not_include_returned_book(monkeypatch):
    fake_db = create_dummy_test_database()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    overdue_books = penalty_routes.get_overdue_books()

    book_titles = [book["book_title"] for book in overdue_books]

    assert "Software Engineering" not in book_titles





def test_scrum_666_overdue_page_loads(client, monkeypatch):
    fake_db = create_dummy_test_database()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/overdue")

    assert response.status_code == 200