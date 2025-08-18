def test_calendar_returns_empty_list(client, auth_header):
    response = client.get('/api/calendar/events', headers=auth_header)
    assert response.status_code == 200
    assert response.get_json() == []
