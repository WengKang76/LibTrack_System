import modules.penalty_transaction.routes as penalty_routes


class FakePenaltyDoc:
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
        return FakePenaltyDoc(self.doc_id, data)

    def update(self, update_data):
        self.records[self.doc_id].update(update_data)


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def stream(self):
        return [
            FakePenaltyDoc(doc_id, data)
            for doc_id, data in self.records.items()
        ]

    def document(self, doc_id):
        return FakeDocumentRef(self.records, doc_id)


class FakeDB:
    def __init__(self):
        self.penalties = {
            "P001": {
                "student_id": "S001",
                "transaction_id": "T001",
                "book_title": "Python Programming",
                "overdue_days": 5,
                "penalty_amount": 5.00,
                "status": "Outstanding"
            },
            "P002": {
                "student_id": "S002",
                "transaction_id": "T002",
                "book_title": "Database System",
                "overdue_days": 3,
                "penalty_amount": 3.00,
                "status": "Paid",
                "payment_method": "Cash",
                "payment_date": "2026-07-14 10:30:00"
            },
            "P003": {
                "student_id": "S003",
                "transaction_id": "T003",
                "book_title": "Software Engineering",
                "overdue_days": 2,
                "penalty_amount": 2.00,
                "status": "Waived"
            }
        }

    def collection(self, collection_name):
        if collection_name == "penalties":
            return FakeCollection(self.penalties)

        return FakeCollection({})


# =========================================================
# SCRUM-681: Record Penalty Payments
# =========================================================

def test_scrum_681_view_payment_records(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    records = penalty_routes.get_penalty_payment_records()

    assert len(records) == 1
    assert records[0]["student_id"] == "S002"
    assert records[0]["status"] == "Paid"
    assert records[0]["payment_method"] == "Cash"


def test_scrum_681_not_include_outstanding_or_waived(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    records = penalty_routes.get_penalty_payment_records()
    titles = [record["book_title"] for record in records]

    assert "Python Programming" not in titles
    assert "Software Engineering" not in titles


def test_scrum_681_payment_records_page_loads(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/librarian/payment-records")

    assert response.status_code == 200


# =========================================================
# SCRUM-682: Waive Penalties
# =========================================================

def test_scrum_682_waive_outstanding_penalty(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.waive_penalty(
        "P001",
        "Approved by librarian due to valid reason.",
        "Librarian"
    )

    assert success is True
    assert fake_db.penalties["P001"]["status"] == "Waived"
    assert fake_db.penalties["P001"]["waived_by"] == "Librarian"
    assert fake_db.penalties["P001"]["waiver_reason"] == "Approved by librarian due to valid reason."


def test_scrum_682_reject_empty_waiver_reason(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.waive_penalty(
        "P001",
        "",
        "Librarian"
    )

    assert success is False
    assert fake_db.penalties["P001"]["status"] == "Outstanding"


def test_scrum_682_reject_paid_penalty(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.waive_penalty(
        "P002",
        "Waive request",
        "Librarian"
    )

    assert success is False
    assert fake_db.penalties["P002"]["status"] == "Paid"


def test_scrum_682_waive_penalty_page_loads(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/librarian/waive/P001")

    assert response.status_code == 200


def test_scrum_682_waive_penalty_route_updates_status(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post("/penalty/librarian/waive/P001", data={
        "waiver_reason": "Approved by librarian due to valid reason.",
        "waived_by": "Librarian"
    })

    assert response.status_code == 302
    assert fake_db.penalties["P001"]["status"] == "Waived"