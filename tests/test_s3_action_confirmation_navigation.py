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

def test_s3_10_penalty_navigation_component_exists():
    html = read_file("templates/components/penalty_navigation.html")

    assert "Penalty Module Navigation" in html
    assert "penalty-nav-card" in html
    assert "penalty-nav-link" in html
    assert "Penalty Records" in html
    assert "Payment Records" in html


def test_s3_10_common_navigation_css_exists():
    css = read_file("static/css/penalty_transaction.css")

    assert ".penalty-nav-card" in css
    assert ".penalty-nav-link" in css
    assert ".penalty-page-actions" in css
    assert ".penalty-btn-warning" in css
    assert ".penalty-btn-danger" in css
    assert ".penalty-btn-secondary" in css
    assert ".button" in css
    assert ".button.secondary" in css
    assert ".button.disabled" in css


def test_s3_10_student_penalty_records_has_navigation():
    html = read_file("modules/penalty_transaction/student/penalty_records.html")

    assert "penalty_navigation.html" in html
    assert 'penalty_nav_role = "student"' in html


def test_s3_10_student_payment_page_has_navigation():
    html = read_file("modules/penalty_transaction/student/pay_credit_card.html")

    assert "penalty_navigation.html" in html
    assert 'penalty_nav_role = "student"' in html


def test_s3_10_librarian_pages_have_navigation():
    waive_html = read_file("modules/penalty_transaction/librarian/waive_penalty.html")
    exception_html = read_file("modules/penalty_transaction/librarian/book_exception.html")

    assert "penalty_navigation.html" in waive_html
    assert 'penalty_nav_role = "librarian"' in waive_html

    assert "penalty_navigation.html" in exception_html
    assert 'penalty_nav_role = "librarian"' in exception_html