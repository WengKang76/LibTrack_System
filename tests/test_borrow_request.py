# SCRUM-16, SCRUM-36, SCRUM-691 and SCRUM-692


def available_book(**changes):
    book = {
        "book_id": "B001",
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "category": "Programming",
        "status": "Available",
        "available_copies": 2,
    }
    book.update(changes)
    return book


def test_available_book_opens_borrow_confirmation(app_factory):
    app = app_factory(books=[available_book()])
    client = app.test_client()

    response = client.get("/catalogue/borrow/B001")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Request to Borrow Book" in page
    assert "Clean Code" in page
    assert "Confirm Borrow Request" in page
    assert 'method="POST"' in page


def test_borrowing_period_is_displayed_before_confirmation(app_factory):
    app = app_factory(books=[available_book()])
    client = app.test_client()

    response = client.get("/catalogue/borrow/B001")
    page = " ".join(response.get_data(as_text=True).split())

    assert response.status_code == 200
    assert "Borrowing Period" in page
    assert "14 days" in page
    assert "after the request is approved" in page


def test_get_request_does_not_create_borrow_request(app_factory):
    app = app_factory(books=[available_book()])
    client = app.test_client()

    response = client.get("/catalogue/borrow/B001")
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert fake_db.collections["borrow_requests"] == []


def test_post_creates_pending_borrow_request(app_factory):
    app = app_factory(books=[available_book()])
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]
    requests = fake_db.collections["borrow_requests"]

    assert response.status_code == 200
    assert "was submitted successfully" in page
    assert len(requests) == 1
    assert requests[0]["student_id"] == "S001"
    assert requests[0]["book_id"] == "B001"
    assert requests[0]["book_title"] == "Clean Code"
    assert requests[0]["status"] == "Pending"
    assert requests[0]["borrowing_period"] == "14 days"
    assert requests[0]["borrowing_period_days"] == 14
    assert requests[0]["request_date"]


def test_unavailable_status_prevents_borrowing(app_factory):
    book = available_book(
        book_id="B002",
        title="Unavailable Book",
        status="Unavailable",
        available_copies=2,
    )
    app = app_factory(books=[book])
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B002",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "This book is unavailable" in page
    assert "Reserve This Book" in page
    assert fake_db.collections["borrow_requests"] == []


def test_zero_available_copies_prevents_borrowing(app_factory):
    book = available_book(
        book_id="B003",
        title="Zero Copy Book",
        status="Available",
        available_copies=0,
    )
    app = app_factory(books=[book])
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B003",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "This book is unavailable" in page
    assert "Unavailable" in page
    assert fake_db.collections["borrow_requests"] == []


def test_duplicate_pending_borrow_request_is_prevented(app_factory):
    existing = [
        {
            "request_id": "BR001",
            "student_id": "S001",
            "book_id": "B001",
            "book_title": "Clean Code",
            "request_date": "2026-07-13 10:00:00",
            "borrowing_period": "14 days",
            "status": "Pending",
        }
    ]
    app = app_factory(
        books=[available_book()],
        borrow_requests=existing,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "already submitted a pending borrow request" in page
    assert len(fake_db.collections["borrow_requests"]) == 1


def test_rejected_request_does_not_block_new_request(app_factory):
    existing = [
        {
            "request_id": "BR001",
            "student_id": "S001",
            "book_id": "B001",
            "book_title": "Clean Code",
            "request_date": "2026-07-10 10:00:00",
            "status": "Rejected",
        }
    ]
    app = app_factory(
        books=[available_book()],
        borrow_requests=existing,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert len(fake_db.collections["borrow_requests"]) == 2
    assert fake_db.collections["borrow_requests"][-1]["status"] == "Pending"


def test_cancelled_request_does_not_block_new_request(app_factory):
    existing = [
        {
            "request_id": "BR001",
            "student_id": "S001",
            "book_id": "B001",
            "book_title": "Clean Code",
            "request_date": "2026-07-10 10:00:00",
            "status": "Cancelled",
        }
    ]
    app = app_factory(
        books=[available_book()],
        borrow_requests=existing,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert len(fake_db.collections["borrow_requests"]) == 2
    assert fake_db.collections["borrow_requests"][-1]["status"] == "Pending"


def test_other_students_pending_request_does_not_block_current_student(
    app_factory,
):
    existing = [
        {
            "request_id": "BR001",
            "student_id": "S999",
            "book_id": "B001",
            "book_title": "Clean Code",
            "request_date": "2026-07-13 10:00:00",
            "status": "Pending",
        }
    ]
    app = app_factory(
        books=[available_book()],
        borrow_requests=existing,
    )
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/B001",
        follow_redirects=True,
    )
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert len(fake_db.collections["borrow_requests"]) == 2
    assert fake_db.collections["borrow_requests"][-1]["student_id"] == "S001"


def test_missing_book_cannot_be_requested(app_factory):
    app = app_factory(books=[])
    client = app.test_client()

    response = client.post(
        "/catalogue/borrow/UNKNOWN",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)
    fake_db = app.extensions["fake_firestore"]

    assert response.status_code == 200
    assert "Book not found." in page
    assert "Book Catalogue" in page
    assert fake_db.collections["borrow_requests"] == []


def test_unsupported_method_is_rejected(app_factory):
    app = app_factory(books=[available_book()])
    client = app.test_client()

    response = client.put("/catalogue/borrow/B001")

    assert response.status_code == 405
