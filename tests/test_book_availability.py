def test_selected_book_availability_route_returns_success(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "category": "Programming",
            "status": "Available",
            "available_copies": 2
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/availability/B001")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Current Availability Status" in page
    assert "Clean Code" in page


def test_available_selected_book_displays_status_and_copy_count(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "category": "Programming",
            "status": "Available",
            "available_copies": 3
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/availability/B001")
    page = response.get_data(as_text=True)
    normalized_page = " ".join(page.split())

    assert response.status_code == 200
    assert "Available" in page
    assert "3 copies are available" in normalized_page
    assert "Request Borrow" in page


def test_unavailable_selected_book_displays_zero_copies(app_factory):
    books = [
        {
            "book_id": "B002",
            "title": "Database Systems",
            "author": "Thomas Connolly",
            "category": "Database",
            "status": "Unavailable",
            "available_copies": 0
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/availability/B002")
    page = response.get_data(as_text=True)
    normalized_page = " ".join(page.split())

    assert response.status_code == 200
    assert "Unavailable" in page
    assert "<dt>Available Copies</dt> <dd class=\"availability-copy-count\"> 0 </dd>" in normalized_page
    assert "Reserve This Book" in page


def test_zero_copies_override_available_status(app_factory):
    books = [
        {
            "book_id": "B003",
            "title": "Zero Copy Book",
            "status": "Available",
            "available_copies": 0
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/availability/B003")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Unavailable" in page
    assert "Reserve This Book" in page
    assert "Request Borrow" not in page


def test_catalogue_contains_view_status_link_for_each_book(app_factory):
    books = [
        {
            "book_id": "B001",
            "title": "Clean Code",
            "status": "Available",
            "available_copies": 1
        }
    ]

    app = app_factory(books)
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "View Status" in page
    assert "/catalogue/availability/B001" in page


def test_missing_selected_book_redirects_to_catalogue(app_factory):
    app = app_factory([])
    client = app.test_client()

    response = client.get(
        "/catalogue/availability/UNKNOWN",
        follow_redirects=True
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Book not found." in page
    assert "Book Catalogue" in page
