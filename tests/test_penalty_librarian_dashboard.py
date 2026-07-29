def test_librarian_penalty_dashboard_lists_all_functions(client):
    response = client.get("/penalty/librarian")

    assert response.status_code == 200
    assert b"Overdue Books" in response.data
    assert b"Outstanding Penalties" in response.data
    assert b"Payment Records" in response.data
    assert b"Waive Penalty" in response.data
    assert b"Return Exceptions" in response.data
    assert b"Lost / Damaged Books" in response.data
    assert b"Borrow Approval Checks" in response.data


def test_librarian_sidebar_links_to_penalty_dashboard(client):
    with client.session_transaction() as user_session:
        user_session["user_id"] = "LIB001"
        user_session["role"] = "librarian"
        user_session["full_name"] = "Test Librarian"

    response = client.get("/penalty/librarian")

    assert b'href="/penalty/librarian"' in response.data
