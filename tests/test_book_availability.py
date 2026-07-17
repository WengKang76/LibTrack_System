# SCRUM-685: View current availability status through book details


def detailed_book(**changes):
    book = {
        "book_id": "B001",
        "title": "Python Programming",
        "author": "Sherman",
        "isbn": "9780000000001",
        "category": "Programming",
        "publisher": "Technology Press",
        "publication_year": "2024",
        "total_copies": 5,
        "available_copies": 3,
        "status": "Available",
    }
    book.update(changes)
    return book


def test_book_details_page_uses_student_catalogue_information(app_factory):
    app = app_factory(books=[detailed_book()])
    client = app.test_client()

    response = client.get("/catalogue/details/B001")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Python Programming" in page
    assert "Sherman" in page
    assert "9780000000001" in page
    assert "Technology Press" in page
    assert "2024" in page
    assert "Total Copies" in page
    assert "Available Copies" in page


def test_available_book_details_show_borrow_action(app_factory):
    app = app_factory(books=[detailed_book()])
    client = app.test_client()

    response = client.get("/catalogue/details/B001")
    page = response.get_data(as_text=True)
    normalised_page = " ".join(page.split())

    assert response.status_code == 200
    assert "Current Availability Status" in page
    assert "Available" in page
    assert "3 copies are available" in normalised_page
    assert "Request Borrow" in page
    assert "/catalogue/borrow/B001" in page
    assert "Reserve This Book" not in page


def test_unavailable_book_details_show_reservation_action(app_factory):
    book = detailed_book(
        book_id="B002",
        title="Database Systems",
        status="Unavailable",
        available_copies=0,
    )
    app = app_factory(books=[book])
    client = app.test_client()

    response = client.get("/catalogue/details/B002")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Database Systems" in page
    assert "Unavailable" in page
    assert "Reserve This Book" in page
    assert "/catalogue/reserve/B002" in page
    assert "Request Borrow" not in page


def test_zero_copies_override_available_status(app_factory):
    book = detailed_book(
        book_id="B003",
        title="Zero Copy Book",
        status="Available",
        available_copies=0,
    )
    app = app_factory(books=[book])
    client = app.test_client()

    response = client.get("/catalogue/details/B003")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Unavailable" in page
    assert "Reserve This Book" in page
    assert "Request Borrow" not in page


def test_catalogue_contains_view_book_details_link(app_factory):
    app = app_factory(books=[detailed_book()])
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "View Book Details" in page
    assert "/catalogue/details/B001" in page


def test_previous_availability_url_uses_same_details_interface(app_factory):
    app = app_factory(books=[detailed_book()])
    client = app.test_client()

    response = client.get("/catalogue/availability/B001")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Python Programming" in page
    assert "Current Availability Status" in page
    assert "Request Borrow" in page


def test_book_details_include_reservation_navigation(app_factory):
    app = app_factory(books=[detailed_book()])
    client = app.test_client()

    response = client.get("/catalogue/details/B001")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "My Reservations" in page
    assert "/catalogue/my-reservations" in page


def test_missing_selected_book_redirects_to_catalogue(app_factory):
    app = app_factory([])
    client = app.test_client()

    response = client.get(
        "/catalogue/details/UNKNOWN",
        follow_redirects=True,
    )
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Book not found." in page
    assert "Book Catalogue" in page
