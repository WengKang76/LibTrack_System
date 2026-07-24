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


def test_scrum_703_pay_outstanding_penalty_with_credit_card(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_credit_card(
        "P001", "4111111111111111"
    )

    assert success is True
    assert fake_db.penalties["P001"]["status"] == "Paid"
    assert fake_db.penalties["P001"]["payment_method"] == "Credit Card"
    assert fake_db.penalties["P001"]["card_last_four"] == "1111"


def test_scrum_703_reject_already_paid_penalty(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_credit_card(
        "P002", "4111111111111111"
    )

    assert success is False
    assert fake_db.penalties["P002"]["status"] == "Paid"


def test_scrum_703_reject_waived_penalty(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_credit_card(
        "P003", "4111111111111111"
    )

    assert success is False
    assert fake_db.penalties["P003"]["status"] == "Waived"


def test_scrum_703_reject_invalid_credit_card(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.pay_penalty_with_credit_card("P001", "123")

    assert success is False
    assert fake_db.penalties["P001"]["status"] == "Outstanding"


def test_scrum_703_credit_card_payment_page_loads(client, monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/student/pay-credit-card/P001")

    assert response.status_code == 200


def test_scrum_703_credit_card_payment_route_updates_status(client, monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post(
        "/penalty/student/pay-credit-card/P001",
        data={
            "card_number": "4111111111111111",
            "card_holder": "Test User",
            "expiry_date": "12/29",
            "cvv": "123",
        },
    )

    assert response.status_code == 302
    assert fake_db.penalties["P001"]["status"] == "Paid"
    assert fake_db.penalties["P001"]["payment_method"] == "Credit Card"
