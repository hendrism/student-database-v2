from app import create_app


def test_health_endpoint(client):
    assert callable(create_app)
    response = client.get('/health')
    assert response.status_code == 200
