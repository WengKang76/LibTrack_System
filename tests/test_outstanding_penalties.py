import modules.penalty_transaction.routes as penalty_routes


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data


class FakeCollection:
    def __init__(self, records):
        self.records = records

    def stream(self):
        return [FakeDoc(doc_id, data) for doc_id, data in self.records.items()]


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


def test_scrum_679_view_outstanding_penalties(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    outstanding_penalties = penalty_routes.get_outstanding_penalties()

    assert len(outstanding_penalties) == 1
    assert outstanding_penalties[0]["student_id"] == "S001"
    assert outstanding_penalties[0]["book_title"] == "Python Programming"
    assert outstanding_penalties[0]["status"] == "Outstanding"


def test_scrum_679_not_include_paid_penalties(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    outstanding_penalties = penalty_routes.get_outstanding_penalties()

    book_titles = [penalty["book_title"] for penalty in outstanding_penalties]

    assert "Database System" not in book_titles


def test_scrum_679_not_include_waived_penalties(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    outstanding_penalties = penalty_routes.get_outstanding_penalties()

    book_titles = [penalty["book_title"] for penalty in outstanding_penalties]

    assert "Software Engineering" not in book_titles


def test_scrum_679_filter_outstanding_penalties_by_student_id(monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    outstanding_penalties = penalty_routes.get_outstanding_penalties("S001")

    assert len(outstanding_penalties) == 1
    assert outstanding_penalties[0]["student_id"] == "S001"


def test_scrum_679_outstanding_penalties_page_loads(client, monkeypatch):
    fake_db = FakeDB()

    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/penalties")

    assert response.status_code == 200
