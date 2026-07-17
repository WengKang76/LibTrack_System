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
                "status": "Rejected"
            },
            "RT003": {
                "student_id": "S003",
                "book_id": "B003",
                "book_title": "Software Engineering",
                "return_date": "2026-07-15",
                "status": "Closed"
            }
        }

        self.penalties = {
            "P001": {
                "student_id": "S002",
                "transaction_id": "RT002",
                "book_title": "Database System",
                "penalty_type": "Rejected Return",
                "penalty_amount": 10.00,
                "status": "Outstanding"
            }
        }

    def collection(self, collection_name):
        if collection_name == penalty_routes.COLLECTION_BORROW_TRANSACTIONS:
            return FakeCollection(self.borrow_transactions)

        if collection_name == "penalties":
            return FakeCollection(self.penalties)

        return FakeCollection({})


# =========================================================
# SCRUM-705: Reject Return Exception
# =========================================================

def test_scrum_705_reject_return_exception_success(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.reject_return_exception(
        "RT001",
        "Returned book condition is unacceptable.",
        "Librarian"
    )

    assert success is True
    assert fake_db.borrow_transactions["RT001"]["status"] == "Rejected"
    assert fake_db.borrow_transactions["RT001"]["return_status"] == "Rejected"
    assert fake_db.borrow_transactions["RT001"]["rejection_reason"] == "Returned book condition is unacceptable."
    assert fake_db.borrow_transactions["RT001"]["rejected_by"] == "Librarian"


def test_scrum_705_reject_empty_reason(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.reject_return_exception(
        "RT001",
        "",
        "Librarian"
    )

    assert success is False
    assert fake_db.borrow_transactions["RT001"]["status"] == "Return Requested"


def test_scrum_705_reject_closed_transaction(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.reject_return_exception(
        "RT003",
        "Invalid return.",
        "Librarian"
    )

    assert success is False
    assert fake_db.borrow_transactions["RT003"]["status"] == "Closed"


def test_scrum_705_reject_return_page_loads(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/librarian/reject-return/RT001")

    assert response.status_code == 200


# =========================================================
# SCRUM-706: Create Penalty Record for Rejected Return
# =========================================================

def test_scrum_706_create_penalty_record_for_rejected_return(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.create_penalty_record_for_rejected_return(
        "RT002",
        "10.00",
        "Return rejected due to unacceptable book condition.",
        "Librarian"
    )

    assert success is False
    assert "already exists" in message


def test_scrum_706_create_new_penalty_after_rejection(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    penalty_routes.reject_return_exception(
        "RT001",
        "Returned book condition is unacceptable.",
        "Librarian"
    )

    success, message = penalty_routes.create_penalty_record_for_rejected_return(
        "RT001",
        "10.00",
        "Returned book condition is unacceptable.",
        "Librarian"
    )

    assert success is True

    created_penalties = [
        penalty
        for penalty in fake_db.penalties.values()
        if penalty.get("transaction_id") == "RT001"
    ]

    assert len(created_penalties) == 1
    assert created_penalties[0]["student_id"] == "S001"
    assert created_penalties[0]["penalty_type"] == "Rejected Return"
    assert created_penalties[0]["penalty_amount"] == 10.00
    assert created_penalties[0]["status"] == "Outstanding"


def test_scrum_706_reject_penalty_if_return_not_rejected(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.create_penalty_record_for_rejected_return(
        "RT001",
        "10.00",
        "Penalty reason.",
        "Librarian"
    )

    assert success is False
    assert fake_db.borrow_transactions["RT001"]["status"] == "Return Requested"


def test_scrum_706_reject_invalid_penalty_amount(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    fake_db.borrow_transactions["RT001"]["status"] = "Rejected"

    success, message = penalty_routes.create_penalty_record_for_rejected_return(
        "RT001",
        "abc",
        "Penalty reason.",
        "Librarian"
    )

    assert success is False


def test_scrum_706_route_rejects_return_and_creates_penalty(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post("/penalty/librarian/reject-return/RT001", data={
        "rejection_reason": "Returned book condition is unacceptable.",
        "penalty_amount": "10.00",
        "rejected_by": "Librarian"
    })

    assert response.status_code == 302
    assert fake_db.borrow_transactions["RT001"]["status"] == "Rejected"

    created_penalties = [
        penalty
        for penalty in fake_db.penalties.values()
        if penalty.get("transaction_id") == "RT001"
    ]

    assert len(created_penalties) == 1
    assert created_penalties[0]["status"] == "Outstanding"