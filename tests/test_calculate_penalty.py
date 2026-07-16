from datetime import date, timedelta

import modules.penalty_transaction.routes as penalty_routes


def test_scrum_678_calculate_one_day_overdue_penalty():
    yesterday = date.today() - timedelta(days=1)

    result = penalty_routes.calculate_penalty_amount(
        yesterday.strftime("%Y-%m-%d")
    )

    assert result["overdue_days"] == 1
    assert result["penalty_amount"] == 1.00


def test_scrum_678_calculate_five_days_overdue_penalty():
    five_days_ago = date.today() - timedelta(days=5)

    result = penalty_routes.calculate_penalty_amount(
        five_days_ago.strftime("%Y-%m-%d")
    )

    assert result["overdue_days"] == 5
    assert result["penalty_amount"] == 5.00


def test_scrum_678_no_penalty_for_future_due_date():
    future_day = date.today() + timedelta(days=3)

    result = penalty_routes.calculate_penalty_amount(
        future_day.strftime("%Y-%m-%d")
    )

    assert result["overdue_days"] == 0
    assert result["penalty_amount"] == 0.00


def test_scrum_678_no_penalty_for_today_due_date():
    today = date.today()

    result = penalty_routes.calculate_penalty_amount(
        today.strftime("%Y-%m-%d")
    )

    assert result["overdue_days"] == 0
    assert result["penalty_amount"] == 0.00