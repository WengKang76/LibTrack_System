import modules.penalty_transaction.routes as penalty_routes


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return self._data


class FakeDocumentRef:
    def __init__(self, records, doc_id):
        self.records = records
        self.doc_id = doc_id

    def get(self):
        data = self.records.get(self.doc_id)
        return FakeDoc(self.doc_id, data)

    def update(self, update_data):
        self.records[self.doc_id].update(update_data)

    def set(self, data):
        self.records[self.doc_id] = data


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def document(self, doc_id):
        return FakeDocumentRef(self.records, doc_id)

    def stream(self):
        return [
            FakeDoc(doc_id, data)
            for doc_id, data in self.records.items()
        ]


class FakeDB:
    def __init__(self):
        self.borrow_transactions = {
            "RT001": {
                "student_id": "S001",
                "book_id": "B001",
                "book_title": "Python Programming",
                "return_date": "2026-07-15",
                "status": "Return Requested"
            },
            "RT002": {
                "student_id": "S002",
                "book_id": "B002",
                "book_title": "Database System",
                "return_date": "2026-07-15",
                "status": "Returned"
            }
        }

        self.book_exceptions = {}

    def collection(self, collection_name):
        if collection_name == penalty_routes.COLLECTION_BORROW_TRANSACTIONS:
            return FakeCollection(self.borrow_transactions)

        if collection_name == "book_exceptions":
            return FakeCollection(self.book_exceptions)

        return FakeCollection({})


# =========================================================
# SCRUM-707: Record Lost or Damaged Book Exception
# =========================================================

def test_scrum_707_record_damaged_book_exception_success(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    success, message = penalty_routes.record_lost_damaged_book_exception(
        "RT001",
        "Damaged",
        "Several pages are torn.",
        "Librarian"
    )

    assert success is True
    assert fake_db.borrow_transactions["RT001"]["status"] == "Damaged Exception Recorded"
    assert fake_db.borrow_transactions["RT001"]["book_exception_status"] == "Exception Recorded"
    assert fake_db.borrow_transactions["RT001"]["exception_type"] == "Damaged"

    created_exceptions = list(fake_db.book_exceptions.values())

    assert len(created_exceptions) == 1
    assert created_exceptions[0]["student_id"] == "S001"
    assert created_exceptions[0]["book_id"] == "B001"
    assert created_exceptions[0]["book_title"] == "Python Programming"
    assert created_exceptions[0]["exception_type"] == "Damaged"
    assert created_exceptions[0]["exception_description"] == "Several pages are torn."
    assert created_exceptions[0]["exception_status"] == "Exception Recorded"
    assert created_exceptions[0]["recorded_by"] == "Librarian"


def test_scrum_707_record_lost_book_exception_success(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    success, message = penalty_routes.record_lost_damaged_book_exception(
        "RT002",
        "Lost",
        "Student reported that the book was lost.",
        "Librarian"
    )

    assert success is True
    assert fake_db.borrow_transactions["RT002"]["status"] == "Lost Exception Recorded"
    assert fake_db.borrow_transactions["RT002"]["exception_type"] == "Lost"

    created_exceptions = list(fake_db.book_exceptions.values())

    assert len(created_exceptions) == 1
    assert created_exceptions[0]["student_id"] == "S002"
    assert created_exceptions[0]["exception_type"] == "Lost"
    assert created_exceptions[0]["exception_description"] == "Student reported that the book was lost."


def test_scrum_707_reject_invalid_exception_type(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    success, message = penalty_routes.record_lost_damaged_book_exception(
        "RT001",
        "Missing",
        "Invalid exception type.",
        "Librarian"
    )

    assert success is False
    assert fake_db.borrow_transactions["RT001"]["status"] == "Return Requested"
    assert len(fake_db.book_exceptions) == 0


def test_scrum_707_reject_empty_exception_description(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    success, message = penalty_routes.record_lost_damaged_book_exception(
        "RT001",
        "Damaged",
        "",
        "Librarian"
    )

    assert success is False
    assert fake_db.borrow_transactions["RT001"]["status"] == "Return Requested"
    assert len(fake_db.book_exceptions) == 0


def test_scrum_707_reject_duplicate_book_exception(monkeypatch):
    fake_db = FakeDB()
    fake_db.book_exceptions["BE001"] = {
        "exception_id": "BE001",
        "transaction_id": "RT001",
        "student_id": "S001",
        "book_id": "B001",
        "book_title": "Python Programming",
        "exception_type": "Damaged",
        "exception_description": "Existing damaged book record.",
        "exception_status": "Exception Recorded"
    }

    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    success, message = penalty_routes.record_lost_damaged_book_exception(
        "RT001",
        "Damaged",
        "Several pages are torn.",
        "Librarian"
    )

    assert success is False
    assert "already exists" in message
    assert len(fake_db.book_exceptions) == 1


def test_scrum_707_book_exception_page_loads(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    response = client.get("/penalty/librarian/book-exception/RT001")

    assert response.status_code == 200


def test_scrum_707_book_exception_route_records_exception(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)
    monkeypatch.setattr(penalty_routes, "DEMO_BOOK_EXCEPTIONS", {})

    response = client.post("/penalty/librarian/book-exception/RT001", data={
        "exception_type": "Damaged",
        "exception_description": "Several pages are torn.",
        "recorded_by": "Librarian"
    })

    assert response.status_code == 302
    assert fake_db.borrow_transactions["RT001"]["status"] == "Damaged Exception Recorded"
    assert fake_db.borrow_transactions["RT001"]["book_exception_status"] == "Exception Recorded"
    assert fake_db.borrow_transactions["RT001"]["exception_type"] == "Damaged"

    created_exceptions = list(fake_db.book_exceptions.values())

    assert len(created_exceptions) == 1
    assert created_exceptions[0]["transaction_id"] == "RT001"
    assert created_exceptions[0]["exception_type"] == "Damaged"
    assert created_exceptions[0]["exception_status"] == "Exception Recorded"