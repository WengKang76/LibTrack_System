import pytest

import modules.book_catalogue.routes as book_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


class FakeDocumentSnapshot:
    def __init__(
        self,
        document_id,
        data,
    ):
        self.id = document_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class FakeBooksCollection:
    def __init__(self, books):
        self.books = books

    def stream(self):
        return [
            FakeDocumentSnapshot(
                document_id,
                book,
            )
            for document_id, book
            in self.books.items()
        ]


class FakeDatabase:
    def __init__(self):
        self.books = {
            "BOOK001": {
                "title": "Clean Code",
                "author": "Robert C. Martin",
                "isbn": "9780132350884",
                "category": "Programming",
                "publisher": "Prentice Hall",
                "publication_year": "2008",
                "is_active": True,
            },
            "BOOK002": {
                "title": "Database System Concepts",
                "author": "Abraham Silberschatz",
                "isbn": "9780078022159",
                "category": "Database",
                "publisher": "McGraw Hill",
                "publication_year": "2019",
                "is_active": True,
            },
            "BOOK003": {
                "title": "Software Engineering",
                "author": "Ian Sommerville",
                "isbn": "9780133943030",
                "category": "Programming",
                "publisher": "Pearson",
                "publication_year": "2016",
                "is_active": False,
            },
            "BOOK004": {
                "title": "Computer Networks",
                "author": "Andrew Tanenbaum",
                "isbn": "9780132126953",
                "category": "Networking",
                "publisher": "Pearson",
                "publication_year": "2011",
                "is_active": False,
            },
        }

    def collection(self, collection_name):
        assert collection_name == "books"

        return FakeBooksCollection(
            self.books
        )


@pytest.fixture
def book_filter_database(
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    monkeypatch.setattr(
        book_routes,
        "_is_book_active",
        lambda book: bool(
            book.get(
                "is_active",
                False,
            )
        ),
    )

    return fake_database


def _page_text(response):
    return response.data.decode(
        "utf-8"
    )


# ============================================================
# SCRUM-1525: FILTER BOOK RECORDS
# ============================================================

def test_scrum_1525_filters_books_by_category(
    client,
    book_filter_database,
):
    response = client.get(
        "/books/?category=programming"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Clean Code" in page_text

    assert (
        "Software Engineering"
        in page_text
    )

    assert (
        "Database System Concepts"
        not in page_text
    )

    assert (
        "Computer Networks"
        not in page_text
    )


def test_scrum_1525_filters_active_books(
    client,
    book_filter_database,
):
    response = client.get(
        "/books/?status=active"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Clean Code" in page_text

    assert (
        "Database System Concepts"
        in page_text
    )

    assert (
        "Software Engineering"
        not in page_text
    )

    assert (
        "Computer Networks"
        not in page_text
    )


def test_scrum_1525_filters_inactive_books(
    client,
    book_filter_database,
):
    response = client.get(
        "/books/?status=inactive"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Software Engineering"
        in page_text
    )

    assert (
        "Computer Networks"
        in page_text
    )

    assert "Clean Code" not in page_text

    assert (
        "Database System Concepts"
        not in page_text
    )


def test_scrum_1525_combines_category_and_status_filters(
    client,
    book_filter_database,
):
    response = client.get(
        (
            "/books/"
            "?category=programming"
            "&status=inactive"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Software Engineering"
        in page_text
    )

    assert "Clean Code" not in page_text

    assert (
        "Database System Concepts"
        not in page_text
    )


def test_scrum_1525_combines_search_and_filters(
    client,
    book_filter_database,
):
    response = client.get(
        (
            "/books/"
            "?q=software"
            "&category=programming"
            "&status=inactive"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Software Engineering"
        in page_text
    )

    assert "Clean Code" not in page_text

    assert (
        "Computer Networks"
        not in page_text
    )


def test_scrum_1525_invalid_filters_default_to_all(
    client,
    book_filter_database,
):
    response = client.get(
        (
            "/books/"
            "?category=unknown-category"
            "&status=unknown-status"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Clean Code" in page_text

    assert (
        "Database System Concepts"
        in page_text
    )

    assert (
        "Software Engineering"
        in page_text
    )

    assert (
        "Computer Networks"
        in page_text
    )


def test_scrum_1525_displays_available_category_options(
    client,
    book_filter_database,
):
    response = client.get(
        "/books/"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "All Categories"
        in page_text
    )

    assert "Programming" in page_text
    assert "Database" in page_text
    assert "Networking" in page_text


def test_scrum_1525_no_matching_filters_displays_message(
    client,
    book_filter_database,
):
    response = client.get(
        (
            "/books/"
            "?category=database"
            "&status=inactive"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "No matching books found"
        in page_text
    )

    assert (
        "Clear Search and Filters"
        in page_text
    )