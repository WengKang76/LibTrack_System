from pathlib import Path

import pytest

import modules.book_catalogue.routes as book_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


BOOK = {
    "book_id": "BOOK001",
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "isbn": "9780132350884",
    "category": "Programming",
}


@pytest.fixture
def detail_environment(
    monkeypatch,
):
    monkeypatch.setattr(
        book_routes,
        "get_book_by_id",
        lambda book_id: dict(BOOK),
    )

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: [],
    )


def test_scrum_1531_back_link_preserves_search(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_q=clean"
            "&return_category=programming"
            "&return_status=active"
            "&return_sort=title_desc"
            "&return_page=3"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert response.status_code == 200

    assert "q=clean" in page_text
    assert "category=programming" in page_text
    assert "status=active" in page_text
    assert "sort=title_desc" in page_text
    assert "page=3" in page_text


def test_scrum_1531_copy_search_preserves_return_search(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_q=database"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert (
        'name="return_q"'
        in page_text
    )

    assert (
        'value="database"'
        in page_text
    )


def test_scrum_1531_preserves_category(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_category=programming"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert (
        'name="return_category"'
        in page_text
    )

    assert (
        'value="programming"'
        in page_text
    )


def test_scrum_1531_preserves_status(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_status=inactive"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert (
        'name="return_status"'
        in page_text
    )

    assert (
        'value="inactive"'
        in page_text
    )


def test_scrum_1531_preserves_sort_option(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_sort=author_desc"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert (
        'name="return_sort"'
        in page_text
    )

    assert (
        'value="author_desc"'
        in page_text
    )


def test_scrum_1531_preserves_page_number(
    client,
    detail_environment,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?return_page=4"
        )
    )

    page_text = response.data.decode(
        "utf-8"
    )

    assert (
        'name="return_page"'
        in page_text
    )

    assert (
        'value="4"'
        in page_text
    )


def test_scrum_1531_manage_books_passes_state_to_details():
    template_text = Path(
        "modules/book_catalogue/"
        "manage_books.html"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert (
        "return_q=search_query"
        in template_text
    )

    assert (
        "return_category=category_filter"
        in template_text
    )

    assert (
        "return_status=status_filter"
        in template_text
    )

    assert (
        "return_sort=sort_option"
        in template_text
    )

    assert (
        "return_page=pagination.current_page"
        in template_text
    )