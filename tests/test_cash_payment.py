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
                "status": "Outstanding",
            },
            "P002": {
                "student_id": "S002",
                "transaction_id": "T002",
                "book_title": "Database System",
                "overdue_days": 3,
                "penalty_amount": 3.00,
                "status": "Paid",
            },
            "P003": {
                "student_id": "S003",
                "transaction_id": "T003",
                "book_title": "Software Engineering",
                "overdue_days": 2,
                "penalty_amount": 2.00,
                "status": "Waived",
            },
        }

    def collection(self, collection_name):
        if collection_name == "penalties":
            return FakeCollection(self.penalties)

        return FakeCollection({})


def test_scrum_680_student_cash_payment_success(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_cash("P001", "10.00")

    assert success is True
    assert fake_db.penalties["P001"]["status"] == "Paid"
    assert fake_db.penalties["P001"]["payment_method"] == "Cash"
    assert fake_db.penalties["P001"]["paid_by"] == "Student"
    assert fake_db.penalties["P001"]["cash_amount_received"] == 10.00
    assert fake_db.penalties["P001"]["change_amount"] == 5.00


def test_scrum_680_reject_insufficient_cash(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_cash("P001", "2.00")

    assert success is False
    assert fake_db.penalties["P001"]["status"] == "Outstanding"


def test_scrum_680_reject_invalid_cash_amount(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_cash("P001", "abc")

    assert success is False
    assert fake_db.penalties["P001"]["status"] == "Outstanding"


def test_scrum_680_reject_already_paid_penalty(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_cash("P002", "5.00")

    assert success is False
    assert fake_db.penalties["P002"]["status"] == "Paid"


def test_scrum_680_reject_waived_penalty(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_cash("P003", "5.00")

    assert success is False
    assert fake_db.penalties["P003"]["status"] == "Waived"


def test_scrum_680_student_cash_payment_page_loads(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/student/pay-cash/P001")

    assert response.status_code == 200


def test_scrum_680_student_cash_payment_route_updates_status(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post(
        "/penalty/student/pay-cash/P001", data={"cash_amount": "10.00"}
    )

    assert response.status_code == 302
    assert fake_db.penalties["P001"]["status"] == "Paid"
    assert fake_db.penalties["P001"]["payment_method"] == "Cash"
    assert fake_db.penalties["P001"]["paid_by"] == "Student"
