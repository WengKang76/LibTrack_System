# Author: Tan Wei Khye

"""
Test cases for Scrum-1679:
Display borrowing records in pages with configurable entries.
"""

from modules.borrowing.services import paginate_records


def test_default_pagination_returns_10_records():
    """
    Given there are 30 records

    When default pagination is applied

    Then only 10 records should be returned
    """

    records = list(range(30))

    result = paginate_records(records)

    assert len(result["records"]) == 10
    assert result["page"] == 1
    assert result["total_pages"] == 3


def test_pagination_with_25_entries():
    """
    Given there are 30 records

    When librarian selects 25 entries per page

    Then 25 records should be returned
    """

    records = list(range(30))

    result = paginate_records(
        records,
        page=1,
        per_page=25,
    )

    assert len(result["records"]) == 25
    assert result["per_page"] == 25


def test_invalid_entries_default_to_10():
    """
    Given librarian provides invalid entries amount

    When pagination runs

    Then system should use 10 entries by default
    """

    records = list(range(30))

    result = paginate_records(
        records,
        page=1,
        per_page=100,
    )

    assert result["per_page"] == 10
