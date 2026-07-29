def test_available_books_route_returns_success(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/catalogue/available")

    assert response.status_code == 200
    assert "Available Books" in response.get_data(as_text=True)


def test_only_available_books_are_displayed(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "category": "Programming",
            "status": "Available",
            "available_copies": 2,
        },
        {
            "book_id": "B002",
            "title": "Unavailable Book",
            "author": "Test Author",
            "category": "Testing",
            "status": "Unavailable",
            "available_copies": 0,
        },
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/available")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Clean Code" in page
    assert "Unavailable Book" not in page


def test_available_books_require_positive_copy_count(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Zero Copy Book",
            "status": "Available",
            "available_copies": 0,
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/available")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Zero Copy Book" not in page
    assert "No available books found." in page


def test_available_books_are_sorted_alphabetically(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Python Programming",
            "status": "Available",
            "available_copies": 1,
        },
        {
            "book_id": "B002",
            "title": "Agile Development",
            "status": "Available",
            "available_copies": 1,
        },
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/available")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.index("Agile Development") < page.index("Python Programming")


def test_available_books_search_filters_results(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "category": "Programming",
            "status": "Available",
            "available_copies": 2,
        },
        {
            "book_id": "B002",
            "title": "Database Systems",
            "author": "Thomas Connolly",
            "category": "Database",
            "status": "Available",
            "available_copies": 1,
        },
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/available?search=database")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Database Systems" in page
    assert "Clean Code" not in page
