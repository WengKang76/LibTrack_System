def test_catalogue_uses_flask_static_stylesheet_once(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/catalogue/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert page.count("/static/css/catalogue_reservation.css") == 1
    assert "../../static/css/catalogue_reservation.css" not in page


def test_catalogue_stylesheet_is_served_by_flask(app_factory):
    app = app_factory()
    client = app.test_client()

    response = client.get("/static/css/catalogue_reservation.css")
    stylesheet = response.get_data(as_text=True)

    assert response.status_code == 200
    assert ".reservation-page" in stylesheet
    assert ".reservation-table" in stylesheet
