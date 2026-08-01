def test_student_penalty_summary_page_displays_payment_options(client):
    with client.session_transaction() as session:
        session.clear()
        session["user_id"] = "S001"
        session["student_id"] = "S001"
        session["full_name"] = "Test Student"
        session["role"] = "student"

    response = client.get("/penalty/student/S001")

    assert response.status_code == 200
    content = response.get_data(as_text=True)
    assert "Penalty Record" in content
    assert "Pay with Credit Card" in content
    assert "Pay with Cash" in content
