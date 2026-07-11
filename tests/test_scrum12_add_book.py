from unittest.mock import MagicMock

import modules.book_catalogue.routes as book_routes


def build_fake_db(existing_isbn=False):
    fake_db = MagicMock()
    collection = fake_db.collection.return_value
    query = collection.where.return_value
    limited_query = query.limit.return_value
    limited_query.stream.return_value = [object()] if existing_isbn else []
    return fake_db, collection


def valid_book_data():
    return {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565",
        "category": "Classic Fiction",
        "total_copies": "4",
    }


def test_scrum_12_add_book_page_loads(client, monkeypatch):
    fake_db, _ = build_fake_db()
    monkeypatch.setattr(book_routes, "db", fake_db)

    response = client.get("/books/add")

    assert response.status_code == 200
    assert b"Add New Book Record" in response.data
    assert b'method="POST"' in response.data


def test_scrum_12_add_book_success(client, monkeypatch):
    fake_db, collection = build_fake_db()
    monkeypatch.setattr(book_routes, "db", fake_db)

    response = client.post("/books/add", data=valid_book_data())

    assert response.status_code == 302
    collection.add.assert_called_once()

    saved_book = collection.add.call_args.args[0]
    assert saved_book["title"] == "The Great Gatsby"
    assert saved_book["author"] == "F. Scott Fitzgerald"
    assert saved_book["isbn"] == "9780743273565"
    assert saved_book["category"] == "Classic Fiction"
    assert saved_book["total_copies"] == 4
    assert saved_book["available_copies"] == 4
    assert saved_book["status"] == "Available"


def test_scrum_12_rejects_missing_required_field(client, monkeypatch):
    fake_db, collection = build_fake_db()
    monkeypatch.setattr(book_routes, "db", fake_db)
    data = valid_book_data()
    data["title"] = ""

    response = client.post("/books/add", data=data)

    assert response.status_code == 400
    assert b"Please fill in all required fields." in response.data
    collection.add.assert_not_called()


def test_scrum_12_rejects_invalid_total_copies(client, monkeypatch):
    fake_db, collection = build_fake_db()
    monkeypatch.setattr(book_routes, "db", fake_db)
    data = valid_book_data()
    data["total_copies"] = "abc"

    response = client.post("/books/add", data=data)

    assert response.status_code == 400
    assert b"Total copies must be a valid whole number." in response.data
    collection.add.assert_not_called()


def test_scrum_12_rejects_zero_total_copies(client, monkeypatch):
    fake_db, collection = build_fake_db()
    monkeypatch.setattr(book_routes, "db", fake_db)
    data = valid_book_data()
    data["total_copies"] = "0"

    response = client.post("/books/add", data=data)

    assert response.status_code == 400
    assert b"Total copies must be at least 1." in response.data
    collection.add.assert_not_called()


def test_scrum_12_rejects_duplicate_isbn(client, monkeypatch):
    fake_db, collection = build_fake_db(existing_isbn=True)
    monkeypatch.setattr(book_routes, "db", fake_db)

    response = client.post("/books/add", data=valid_book_data())

    assert response.status_code == 400
    assert b"A book with this ISBN already exists." in response.data
    collection.add.assert_not_called()
