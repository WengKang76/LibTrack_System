import modules.book_catalogue.routes as book_routes


def _book_records(quantity):
    return [
        {
            "book_id": f"BOOK{number:03d}",
            "title": f"Book {number:03d}",
        }
        for number in range(
            1,
            quantity + 1,
        )
    ]


def test_scrum_1528_invalid_page_defaults_to_first():
    assert (
        book_routes._normalise_page_number(
            "invalid"
        )
        == 1
    )


def test_scrum_1528_negative_page_defaults_to_first():
    assert (
        book_routes._normalise_page_number(
            -5
        )
        == 1
    )


def test_scrum_1528_first_page_contains_ten_books():
    books, pagination = (
        book_routes._paginate_books(
            _book_records(25),
            1,
        )
    )

    assert len(books) == 10
    assert books[0]["book_id"] == "BOOK001"
    assert books[-1]["book_id"] == "BOOK010"
    assert pagination["current_page"] == 1
    assert pagination["total_pages"] == 3


def test_scrum_1528_second_page_contains_next_ten_books():
    books, pagination = (
        book_routes._paginate_books(
            _book_records(25),
            2,
        )
    )

    assert len(books) == 10
    assert books[0]["book_id"] == "BOOK011"
    assert books[-1]["book_id"] == "BOOK020"
    assert pagination["start_item"] == 11
    assert pagination["end_item"] == 20


def test_scrum_1528_last_page_contains_remaining_books():
    books, pagination = (
        book_routes._paginate_books(
            _book_records(25),
            3,
        )
    )

    assert len(books) == 5
    assert books[0]["book_id"] == "BOOK021"
    assert books[-1]["book_id"] == "BOOK025"
    assert pagination["has_next"] is False


def test_scrum_1528_page_above_range_uses_last_page():
    books, pagination = (
        book_routes._paginate_books(
            _book_records(25),
            99,
        )
    )

    assert pagination["current_page"] == 3
    assert books[0]["book_id"] == "BOOK021"


def test_scrum_1528_empty_results_are_handled():
    books, pagination = (
        book_routes._paginate_books(
            [],
            1,
        )
    )

    assert books == []
    assert pagination["total_items"] == 0
    assert pagination["total_pages"] == 1
    assert pagination["start_item"] == 0
    assert pagination["end_item"] == 0


def test_scrum_1528_previous_and_next_metadata():
    _, pagination = (
        book_routes._paginate_books(
            _book_records(25),
            2,
        )
    )

    assert pagination["has_previous"] is True
    assert pagination["has_next"] is True
    assert pagination["previous_page"] == 1
    assert pagination["next_page"] == 3


def test_scrum_1528_supports_custom_page_size():
    books, pagination = (
        book_routes._paginate_books(
            _book_records(12),
            2,
            per_page=5,
        )
    )

    assert len(books) == 5
    assert books[0]["book_id"] == "BOOK006"
    assert pagination["total_pages"] == 3
    