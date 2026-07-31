# SCRUM-1195: Keep request, transaction, reservation, and inventory consistent

import modules.borrowing.services as borrowing_services


def _install_approval_repository(monkeypatch, reservation_failure=False):
    state = {
        "request": {
            "id": "BR001",
            "student_id": "S001",
            "book_id": "B001",
            "status": "Pending",
            "reservation_id": "R001",
        },
        "book": {
            "id": "B001",
            "title": "Data Engineering",
            "status": "Available",
            "available_copies": 1,
            "total_copies": 1,
        },
        "reservation": {
            "id": "R001",
            "student_id": "S001",
            "book_id": "B001",
            "status": "Borrow Request Submitted",
            "borrowing_request_id": "BR001",
        },
        "transactions": {},
    }

    monkeypatch.setattr(
        borrowing_services,
        "find_request",
        lambda request_id: state["request"] if request_id == "BR001" else None,
    )
    monkeypatch.setattr(
        borrowing_services,
        "update_request_status",
        lambda _request_id, status: state["request"].update({"status": status}),
    )
    monkeypatch.setattr(
        borrowing_services,
        "find_book",
        lambda book_id: state["book"] if book_id == "B001" else None,
    )
    monkeypatch.setattr(
        borrowing_services,
        "update_book",
        lambda _book_id, updates: state["book"].update(updates),
    )
    monkeypatch.setattr(
        borrowing_services,
        "find_reservation",
        lambda reservation_id: (
            state["reservation"] if reservation_id == "R001" else None
        ),
    )

    def update_reservation(_reservation_id, updates):
        if reservation_failure:
            raise RuntimeError("simulated reservation update failure")
        state["reservation"].update(updates)

    monkeypatch.setattr(
        borrowing_services,
        "update_reservation",
        update_reservation,
    )

    def add_transaction(transaction):
        state["transactions"]["BT001"] = transaction.copy()
        return "BT001"

    monkeypatch.setattr(
        borrowing_services,
        "add_borrow_transaction",
        add_transaction,
    )
    monkeypatch.setattr(
        borrowing_services,
        "delete_borrow_transaction",
        lambda transaction_id: state["transactions"].pop(
            transaction_id,
            None,
        ),
    )

    return state


def test_approval_synchronises_all_cross_module_records(monkeypatch):
    state = _install_approval_repository(monkeypatch)

    transaction_id = borrowing_services.approve_borrow_request("BR001")

    assert transaction_id == "BT001"
    assert state["request"]["status"] == "Approved"
    assert state["book"]["available_copies"] == 0
    assert state["book"]["status"] == "Unavailable"
    assert state["transactions"]["BT001"]["request_id"] == "BR001"
    assert state["transactions"]["BT001"]["reservation_id"] == "R001"
    assert state["reservation"]["status"] == "Fulfilled"
    assert state["reservation"]["borrowing_transaction_id"] == "BT001"


def test_unavailable_book_prevents_approval_without_partial_updates(monkeypatch):
    state = _install_approval_repository(monkeypatch)
    state["book"]["available_copies"] = 0
    state["book"]["status"] = "Unavailable"

    result = borrowing_services.approve_borrow_request("BR001")

    assert result is False
    assert state["request"]["status"] == "Pending"
    assert state["reservation"]["status"] == "Borrow Request Submitted"
    assert state["transactions"] == {}


def test_failed_reservation_sync_rolls_back_other_updates(monkeypatch):
    state = _install_approval_repository(
        monkeypatch,
        reservation_failure=True,
    )

    result = borrowing_services.approve_borrow_request("BR001")

    assert result is False
    assert state["request"]["status"] == "Pending"
    assert state["book"]["available_copies"] == 1
    assert state["book"]["status"] == "Available"
    assert state["transactions"] == {}


def test_confirmed_return_restores_book_availability(monkeypatch):
    transaction = {
        "id": "BT001",
        "student_id": "S001",
        "book_id": "B001",
        "status": "Return Pending",
    }
    book = {
        "id": "B001",
        "status": "Unavailable",
        "available_copies": 0,
        "total_copies": 1,
    }

    monkeypatch.setattr(
        borrowing_services,
        "find_borrow_transaction",
        lambda transaction_id: transaction if transaction_id == "BT001" else None,
    )
    monkeypatch.setattr(
        borrowing_services,
        "update_borrow_transaction",
        lambda _transaction_id, updates: transaction.update(updates),
    )
    monkeypatch.setattr(
        borrowing_services,
        "find_book",
        lambda book_id: book if book_id == "B001" else None,
    )
    monkeypatch.setattr(
        borrowing_services,
        "update_book",
        lambda _book_id, updates: book.update(updates),
    )

    result = borrowing_services.confirm_book_return("BT001")

    assert result is True
    assert transaction["status"] == "Returned"
    assert book["available_copies"] == 1
    assert book["status"] == "Available"
