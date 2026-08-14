from pathlib import Path

import modules.book_catalogue.routes as book_routes


def test_scrum_1529_zero_copies_requires_attention():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": 0,
            }
        )
    )

    assert details["available_count"] == 0
    assert (
        details["availability_level"]
        == "zero"
    )
    assert (
        details["availability_label"]
        == "No Copies Available"
    )
    assert details["needs_attention"] is True


def test_scrum_1529_negative_count_is_treated_as_zero():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": -3,
            }
        )
    )

    assert details["available_count"] == 0
    assert (
        details["availability_level"]
        == "zero"
    )


def test_scrum_1529_one_copy_is_low_availability():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": 1,
            }
        )
    )

    assert (
        details["availability_level"]
        == "low"
    )
    assert (
        details["availability_label"]
        == "Low Availability"
    )
    assert details["needs_attention"] is True


def test_scrum_1529_threshold_count_is_low():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": (
                    book_routes
                    .LOW_AVAILABILITY_THRESHOLD
                ),
            }
        )
    )

    assert (
        details["availability_level"]
        == "low"
    )


def test_scrum_1529_count_above_threshold_is_normal():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": 3,
            }
        )
    )

    assert (
        details["availability_level"]
        == "normal"
    )
    assert details["needs_attention"] is False


def test_scrum_1529_accepts_numeric_string_count():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": "2",
            }
        )
    )

    assert details["available_count"] == 2
    assert (
        details["availability_level"]
        == "low"
    )


def test_scrum_1529_invalid_count_defaults_to_zero():
    details = (
        book_routes
        ._book_availability_details(
            {
                "available_copies": "invalid",
            }
        )
    )

    assert details["available_count"] == 0
    assert (
        details["availability_level"]
        == "zero"
    )


def test_scrum_1529_template_contains_availability_indicator():
    template_path = Path(
        "modules/book_catalogue/"
        "manage_books.html"
    )

    template_text = (
        template_path.read_text(
            encoding="utf-8-sig"
        )
    )

    assert "<th>Availability</th>" in template_text
    assert "availability-badge" in template_text
    assert (
        "availability-alert-text"
        in template_text
    )