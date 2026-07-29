def test_catalogue_blueprint_is_registered(app_factory):
    app = app_factory()

    assert "catalogue_reservation" in app.blueprints


def test_catalogue_route_returns_success(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/catalogue/")

    assert response.status_code == 200
    assert "Book Catalogue" in response.get_data(as_text=True)


def test_catalogue_displays_available_and_unavailable_books(app_factory):
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
            "status": "Unavailable",
            "available_copies": 0,
        },
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Clean Code" in page
    assert "Database Systems" in page


def test_catalogue_search_filters_books(app_factory):
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

    response = client.get("/catalogue/?search=clean")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Clean Code" in page
    assert "Database Systems" not in page
