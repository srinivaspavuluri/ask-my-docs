from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_search_rejects_empty_question():
    response = client.get("/search", params={"q": " "})
    assert response.status_code == 400

