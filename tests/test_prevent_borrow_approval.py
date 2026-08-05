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
        return [FakeDoc(doc_id, data) for doc_id, data in self.records.items()]


class FakeDB:
    def __init__(self):
        self.borrow_requests = {
            "BR001": {
                "request_id": "BR001",
                "student_id": "S001",
                "book_id": "B001",
                "book_title": "Python Programming",
                "request_date": "2026-07-15",
                "status": "Pending",
            },
            "BR002": {
                "request_id": "BR002",
                "student_id": "S002",
                "book_id": "B002",
                "book_title": "Database System",
                "request_date": "2026-07-15",
                "status": "Pending",
            },
            "BR003": {
                "request_id": "BR003",
                "student_id": "S003",
                "book_id": "B003",
                "book_title": "Software Engineering",
                "request_date": "2026-07-15",
                "status": "Approved",
            },
        }

        self.penalties = {
            "P001": {
                "penalty_id": "P001",
                "student_id": "S001",
                "book_title": "Python Programming",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 5.00,
                "status": "Outstanding",
            },
            "P002": {
                "penalty_id": "P002",
                "student_id": "S002",
                "book_title": "Database System",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 3.00,
                "status": "Paid",
            },
            "P003": {
                "penalty_id": "P003",
                "student_id": "S003",
                "book_title": "Software Engineering",
                "penalty_type": "Overdue Penalty",
                "penalty_amount": 2.00,
                "status": "Waived",
            },
        }

    def collection(self, collection_name):
        if collection_name == "borrow_requests":
            return FakeCollection(self.borrow_requests)

        if collection_name == "penalties":
            return FakeCollection(self.penalties)

        return FakeCollection({})


# =========================================================
# SCRUM-709: Prevent Borrowing Approval for Unpaid Penalties
# =========================================================


def test_scrum_709_get_unpaid_penalties_by_student(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    unpaid_penalties = penalty_routes.get_unpaid_penalties_by_student("S001")

    assert len(unpaid_penalties) == 1
    assert unpaid_penalties[0]["student_id"] == "S001"
    assert unpaid_penalties[0]["status"] == "Outstanding"
    assert unpaid_penalties[0]["penalty_amount"] == 5.00


def test_scrum_709_no_unpaid_penalties_for_paid_student(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    unpaid_penalties = penalty_routes.get_unpaid_penalties_by_student("S002")

    assert len(unpaid_penalties) == 0


def test_scrum_709_block_borrow_approval_when_unpaid_penalty_exists(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR001", "Librarian"
    )

    assert success is False
    assert "unpaid penalties" in message
    assert fake_db.borrow_requests["BR001"]["status"] == "Pending"


def test_scrum_709_approve_borrow_request_when_no_unpaid_penalty(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR002", "Librarian"
    )

    assert success is True
    assert fake_db.borrow_requests["BR002"]["status"] == "Approved"
    assert fake_db.borrow_requests["BR002"]["approved_by"] == "Librarian"
    assert "approved successfully" in message


def test_scrum_709_reject_non_pending_borrow_request(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR003", "Librarian"
    )

    assert success is False
    assert fake_db.borrow_requests["BR003"]["status"] == "Approved"


def test_scrum_709_reject_missing_borrow_request(monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    success, message = penalty_routes.approve_borrow_request_with_penalty_check(
        "BR999", "Librarian"
    )

    assert success is False
    assert message == "Borrow request not found."


def test_scrum_709_check_borrow_approval_page_loads_for_blocked_student(
    client, monkeypatch
):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/librarian/check-borrow-approval/BR001")

    assert response.status_code == 200


def test_scrum_709_check_borrow_approval_page_loads_for_allowed_student(
    client, monkeypatch
):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.get("/penalty/librarian/check-borrow-approval/BR002")

    assert response.status_code == 200


def test_scrum_709_route_approves_student_without_unpaid_penalty(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post(
        "/penalty/librarian/check-borrow-approval/BR002",
        data={"approved_by": "Librarian"},
    )

    assert response.status_code == 302
    assert fake_db.borrow_requests["BR002"]["status"] == "Approved"
    assert fake_db.borrow_requests["BR002"]["approved_by"] == "Librarian"


def test_scrum_709_route_blocks_student_with_unpaid_penalty(client, monkeypatch):
    fake_db = FakeDB()
    monkeypatch.setattr(penalty_routes, "db", fake_db)

    response = client.post(
        "/penalty/librarian/check-borrow-approval/BR001",
        data={"approved_by": "Librarian"},
    )

    assert response.status_code == 400
    assert fake_db.borrow_requests["BR001"]["status"] == "Pending"
