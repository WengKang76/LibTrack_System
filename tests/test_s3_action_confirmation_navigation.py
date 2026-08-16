from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


def read_file(relative_path):
    file_path = BASE_DIR / relative_path
    assert file_path.exists(), f"{relative_path} does not exist."
    return file_path.read_text(encoding="utf-8")


# =========================================================
# SCRUM-S3-07 — Add Librarian Penalty Action Confirmation
# =========================================================

def test_s3_07_action_confirmation_component_exists():
    html = read_file("templates/components/penalty_action_confirmation.html")

    assert "confirmPenaltyAction" in html
    assert "Please confirm this action" in html
    assert "This action may update the penalty record" in html


def test_s3_07_waive_penalty_page_uses_confirmation():
    html = read_file("modules/penalty_transaction/librarian/waive_penalty.html")

    assert "confirmPenaltyAction" in html
    assert "Waive Penalty" in html
    assert "penalty_action_confirmation.html" in html


def test_s3_07_book_exception_page_uses_confirmation():
    html = read_file("modules/penalty_transaction/librarian/book_exception.html")

    assert "confirmPenaltyAction" in html
    assert "Record Lost or Damaged Book Exception" in html
    assert "penalty_action_confirmation.html" in html


def test_s3_07_reject_return_page_uses_confirmation():
    html = read_file("modules/penalty_transaction/librarian/reject_return_exception.html")

    assert "confirmPenaltyAction" in html
    assert "Reject Return and Create Penalty" in html
    assert "penalty_action_confirmation.html" in html


# =========================================================
# SCRUM-S3-10 — Consistent Penalty Module Navigation and Design
# =========================================================







