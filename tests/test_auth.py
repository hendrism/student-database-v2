def test_profile_requires_token(client):
    response = client.get('/auth/profile', headers={'Authorization': 'Bearer invalid'})
    assert response.status_code == 401
