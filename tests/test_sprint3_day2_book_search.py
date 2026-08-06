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
                "catalogue_status": "Active",
            },
            "BOOK002": {
                "title": "Database System Concepts",
                "author": "Abraham Silberschatz",
                "isbn": "9780078022159",
                "category": "Database",
                "publisher": "McGraw Hill",
                "publication_year": "2019",
                "catalogue_status": "Active",
            },
            "BOOK003": {
                "title": "Software Engineering",
                "author": "Ian Sommerville",
                "isbn": "9780133943030",
                "category": "Software Engineering",
                "publisher": "Pearson",
                "publication_year": "2016",
                "catalogue_status": "Inactive",
            },
        }

    def collection(self, collection_name):
        assert collection_name == "books"

        return FakeBooksCollection(
            self.books
        )


@pytest.fixture
def book_search_database(
    monkeypatch,
):
    fake_database = FakeDatabase()

    monkeypatch.setattr(
        book_routes,
        "db",
        fake_database,
    )

    return fake_database


def _page_text(response):
    return response.data.decode(
        "utf-8"
    )


# ============================================================
# SCRUM-1523: SEARCH BOOK RECORDS
# ============================================================

def test_scrum_1523_searches_by_partial_title_case_insensitively(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=CLEAN"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Clean Code" in page_text

    assert (
        "Database System Concepts"
        not in page_text
    )

    assert (
        "Software Engineering"
        not in page_text
    )


def test_scrum_1523_searches_by_author(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=silberschatz"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Database System Concepts"
        in page_text
    )

    assert "Clean Code" not in page_text


def test_scrum_1523_searches_by_isbn(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=9780133943030"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Software Engineering"
        in page_text
    )

    assert "Clean Code" not in page_text


def test_scrum_1523_searches_by_category(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=database"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Database System Concepts"
        in page_text
    )

    assert "Clean Code" not in page_text


def test_scrum_1523_searches_by_publisher(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=pearson"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Software Engineering"
        in page_text
    )

    assert (
        "Database System Concepts"
        not in page_text
    )


def test_scrum_1523_searches_by_publication_year(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=2008"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Clean Code" in page_text

    assert (
        "Software Engineering"
        not in page_text
    )


def test_scrum_1523_unknown_search_displays_clear_message(
    client,
    book_search_database,
):
    response = client.get(
        "/books/?q=unknown-book"
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "No matching books found"
        in page_text
    )

    assert "Clear Search" in page_text

    assert (
        'value="unknown-book"'
        in page_text
    )


def test_scrum_1523_blank_search_displays_all_books_in_title_order(
    client,
    book_search_database,
):
    response = client.get(
        "/books/"
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
        page_text.index("Clean Code")
        < page_text.index(
            "Database System Concepts"
        )
        < page_text.index(
            "Software Engineering"
        )
    )