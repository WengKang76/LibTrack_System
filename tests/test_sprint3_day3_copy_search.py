import pytest

import modules.book_catalogue.routes as book_routes


pytestmark = pytest.mark.usefixtures(
    "login_as_librarian"
)


BOOK_RECORD = {
    "book_id": "BOOK001",
    "title": "Clean Code",
    "author": "Robert C. Martin",
    "isbn": "9780132350884",
    "category": "Programming",
    "publisher": "Prentice Hall",
    "publication_year": "2008",
}


COPY_RECORDS = [
    {
        "document_id": "COPY-BOOK001-001",
        "copy_id": "COPY-BOOK001-001",
        "book_id": "BOOK001",
        "copy_number": 1,
        "status": "Available",
        "condition": "Good",
        "created_at": "2026-08-01 09:00:00",
    },
    {
        "document_id": "COPY-BOOK001-002",
        "copy_id": "COPY-BOOK001-002",
        "book_id": "BOOK001",
        "copy_number": 2,
        "status": "Borrowed",
        "condition": "Good",
        "created_at": "2026-08-01 09:01:00",
    },
    {
        "document_id": "COPY-BOOK001-003",
        "copy_id": "COPY-BOOK001-003",
        "book_id": "BOOK001",
        "copy_number": 3,
        "status": "Damaged",
        "condition": "Damaged",
        "created_at": "2026-08-01 09:02:00",
    },
]


@pytest.fixture
def copy_search_records(
    monkeypatch,
):
    monkeypatch.setattr(
        book_routes,
        "get_book_by_id",
        lambda book_id: (
            dict(BOOK_RECORD)
            if book_id == "BOOK001"
            else None
        ),
    )

    monkeypatch.setattr(
        book_routes,
        "_get_book_copies",
        lambda book_id: [
            dict(copy_record)
            for copy_record in COPY_RECORDS
        ],
    )

    return COPY_RECORDS


def _page_text(response):
    return response.data.decode(
        "utf-8"
    )


# ============================================================
# SCRUM-1524: SEARCH INDIVIDUAL COPIES BY COPY ID
# ============================================================

def test_scrum_1524_searches_by_complete_copy_id(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=COPY-BOOK001-002"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-002" in page_text
    assert "COPY-BOOK001-001" not in page_text
    assert "COPY-BOOK001-003" not in page_text


def test_scrum_1524_searches_by_partial_copy_id(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=003"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-003" in page_text
    assert "COPY-BOOK001-001" not in page_text
    assert "COPY-BOOK001-002" not in page_text


def test_scrum_1524_search_is_case_insensitive(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=copy-book001-001"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-001" in page_text
    assert "COPY-BOOK001-002" not in page_text


def test_scrum_1524_blank_search_displays_all_copies(
    client,
    copy_search_records,
):
    response = client.get(
        "/books/details/BOOK001"
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-001" in page_text
    assert "COPY-BOOK001-002" in page_text
    assert "COPY-BOOK001-003" in page_text


def test_scrum_1524_unknown_copy_displays_clear_message(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=UNKNOWN-COPY"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "No matching physical copies found"
        in page_text
    )

    assert "Clear Search" in page_text

    assert (
        'value="UNKNOWN-COPY"'
        in page_text
    )


def test_scrum_1524_displays_filtered_and_total_counts(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=002"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "Showing"
        in page_text
    )

    assert (
        "of"
        in page_text
    )

    assert (
        "physical copies"
        in page_text
    )


def test_scrum_1524_does_not_search_by_status(
    client,
    copy_search_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=Borrowed"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "No matching physical copies found"
        in page_text
    )

    assert "COPY-BOOK001-002" not in page_text


def test_scrum_1524_unknown_book_returns_404(
    client,
    copy_search_records,
):
    response = client.get(
        "/books/details/UNKNOWN"
    )

    assert response.status_code == 404

    assert (
        b"Book record not found"
        in response.data
    )