import pytest

from modules.book_catalogue.routes import (
    _validate_inventory_counts,
)


# ============================================================
# SCRUM-1184: VALID INVENTORY COUNTS
# ============================================================

@pytest.mark.parametrize(
    (
        "total_copies",
        "available_copies",
    ),
    [
        (0, 0),
        (1, 0),
        (1, 1),
        (5, 0),
        (5, 3),
        (5, 5),
        ("5", "3"),
    ],
)
def test_scrum_1184_accepts_valid_counts(
    total_copies,
    available_copies,
):
    error = _validate_inventory_counts(
        total_copies,
        available_copies,
    )

    assert error is None


# ============================================================
# SCRUM-1184: NEGATIVE COUNT PREVENTION
# ============================================================

def test_scrum_1184_rejects_negative_total():
    error = _validate_inventory_counts(
        -1,
        0,
    )

    assert error == (
        "Total copies cannot be negative."
    )


def test_scrum_1184_rejects_negative_available():
    error = _validate_inventory_counts(
        5,
        -1,
    )

    assert error == (
        "Available copies cannot be negative."
    )


# ============================================================
# SCRUM-1184: AVAILABLE CANNOT EXCEED TOTAL
# ============================================================

def test_scrum_1184_rejects_available_above_total():
    error = _validate_inventory_counts(
        5,
        6,
    )

    assert error == (
        "Available copies cannot be greater "
        "than total copies."
    )


def test_scrum_1184_rejects_available_when_total_zero():
    error = _validate_inventory_counts(
        0,
        1,
    )

    assert error == (
        "Available copies cannot be greater "
        "than total copies."
    )


# ============================================================
# SCRUM-1184: INVALID DATA TYPES
# ============================================================

@pytest.mark.parametrize(
    (
        "total_copies",
        "available_copies",
    ),
    [
        ("invalid", 1),
        (5, "invalid"),
        (None, 1),
        (5, None),
        (True, 1),
        (5, False),
    ],
)
def test_scrum_1184_rejects_invalid_values(
    total_copies,
    available_copies,
):
    error = _validate_inventory_counts(
        total_copies,
        available_copies,
    )

    assert error is not None