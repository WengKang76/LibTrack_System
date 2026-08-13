import modules.book_catalogue.routes as book_routes


BOOKS = [
    {
        "book_id": "BOOK001",
        "title": "Alpha Programming",
        "author": "Zed Author",
        "publication_year": "2010",
        "created_at": "2026-01-02 09:00:00",
        "available_copies": 2,
    },
    {
        "book_id": "BOOK002",
        "title": "Beta Database",
        "author": "Amy Writer",
        "publication_year": "2020",
        "created_at": "2026-01-03 09:00:00",
        "available_copies": 0,
    },
    {
        "book_id": "BOOK003",
        "title": "Gamma Software",
        "author": "Bob Developer",
        "publication_year": "",
        "created_at": "",
        "available_copies": 5,
    },
]


def _sorted_titles(sort_option):
    books = [
        dict(book)
        for book in BOOKS
    ]

    book_routes._sort_books(
        books,
        sort_option,
    )

    return [
        book["title"]
        for book in books
    ]


def test_scrum_1527_sorts_title_ascending():
    assert _sorted_titles(
        "title_asc"
    ) == [
        "Alpha Programming",
        "Beta Database",
        "Gamma Software",
    ]


def test_scrum_1527_sorts_title_descending():
    assert _sorted_titles(
        "title_desc"
    ) == [
        "Gamma Software",
        "Beta Database",
        "Alpha Programming",
    ]


def test_scrum_1527_sorts_author_ascending():
    assert _sorted_titles(
        "author_asc"
    ) == [
        "Beta Database",
        "Gamma Software",
        "Alpha Programming",
    ]


def test_scrum_1527_sorts_author_descending():
    assert _sorted_titles(
        "author_desc"
    ) == [
        "Alpha Programming",
        "Gamma Software",
        "Beta Database",
    ]


def test_scrum_1527_sorts_publication_year_newest():
    assert _sorted_titles(
        "publication_year_newest"
    ) == [
        "Beta Database",
        "Alpha Programming",
        "Gamma Software",
    ]


def test_scrum_1527_sorts_publication_year_oldest():
    assert _sorted_titles(
        "publication_year_oldest"
    ) == [
        "Alpha Programming",
        "Beta Database",
        "Gamma Software",
    ]


def test_scrum_1527_sorts_date_added_newest():
    assert _sorted_titles(
        "date_added_newest"
    ) == [
        "Beta Database",
        "Alpha Programming",
        "Gamma Software",
    ]


def test_scrum_1527_sorts_date_added_oldest():
    assert _sorted_titles(
        "date_added_oldest"
    ) == [
        "Alpha Programming",
        "Beta Database",
        "Gamma Software",
    ]


def test_scrum_1527_sorts_available_copies_highest():
    assert _sorted_titles(
        "available_copies_highest"
    ) == [
        "Gamma Software",
        "Alpha Programming",
        "Beta Database",
    ]


def test_scrum_1527_sorts_available_copies_lowest():
    assert _sorted_titles(
        "available_copies_lowest"
    ) == [
        "Beta Database",
        "Alpha Programming",
        "Gamma Software",
    ]


def test_scrum_1527_invalid_option_defaults_to_title():
    assert _sorted_titles(
        "invalid-option"
    ) == [
        "Alpha Programming",
        "Beta Database",
        "Gamma Software",
    ]
    