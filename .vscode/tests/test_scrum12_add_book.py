def test_add_book_success(client):
    book_data = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "isbn": "9780743273565"
    }
    response = client.post("/books/add", data=book_data)
    assert response.status_code in [200, 302]
