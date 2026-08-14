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
        "status": "Reserved",
        "condition": "Good",
        "created_at": "2026-08-01 09:02:00",
    },
    {
        "document_id": "COPY-BOOK001-004",
        "copy_id": "COPY-BOOK001-004",
        "book_id": "BOOK001",
        "copy_number": 4,
        "status": "Damaged",
        "condition": "Damaged",
        "created_at": "2026-08-01 09:03:00",
    },
    {
        "document_id": "COPY-BOOK001-005",
        "copy_id": "COPY-BOOK001-005",
        "book_id": "BOOK001",
        "copy_number": 5,
        "status": "Lost",
        "condition": "Unknown",
        "created_at": "2026-08-01 09:04:00",
    },
]


@pytest.fixture
def copy_filter_records(
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
# SCRUM-1526: FILTER INDIVIDUAL BOOK COPIES
# ============================================================

def test_scrum_1526_filters_available_copies(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=available"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-001" in page_text
    assert "COPY-BOOK001-002" not in page_text
    assert "COPY-BOOK001-003" not in page_text
    assert "COPY-BOOK001-004" not in page_text
    assert "COPY-BOOK001-005" not in page_text


def test_scrum_1526_filters_borrowed_copies(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=borrowed"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-002" in page_text
    assert "COPY-BOOK001-001" not in page_text


def test_scrum_1526_filters_reserved_copies(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=reserved"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-003" in page_text
    assert "COPY-BOOK001-002" not in page_text


def test_scrum_1526_filters_damaged_copies(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=damaged"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-004" in page_text
    assert "COPY-BOOK001-005" not in page_text


def test_scrum_1526_filters_lost_copies(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=lost"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-005" in page_text
    assert "COPY-BOOK001-004" not in page_text


def test_scrum_1526_combines_copy_id_search_and_status_filter(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=004"
            "&copy_status=damaged"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "COPY-BOOK001-004" in page_text
    assert "COPY-BOOK001-001" not in page_text
    assert "COPY-BOOK001-005" not in page_text


def test_scrum_1526_invalid_status_defaults_to_all(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=unknown-status"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    for copy_record in COPY_RECORDS:
        assert (
            copy_record["copy_id"]
            in page_text
        )


def test_scrum_1526_no_matching_filter_displays_message(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_q=002"
            "&copy_status=lost"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        "No matching physical copies found"
        in page_text
    )

    assert (
        "Clear Search and Filter"
        in page_text
    )


def test_scrum_1526_preserves_selected_status(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=reserved"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200

    assert (
        'value="reserved"'
        in page_text
    )

    assert "selected" in page_text


def test_scrum_1526_displays_filtered_and_total_counts(
    client,
    copy_filter_records,
):
    response = client.get(
        (
            "/books/details/BOOK001"
            "?copy_status=damaged"
        )
    )

    page_text = _page_text(response)

    assert response.status_code == 200
    assert "Showing" in page_text
    assert "physical copies" in page_text
    assert "Damaged" in page_text