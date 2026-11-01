from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ask_rejects_empty_question():
    response = client.post("/ask", json={"question" : " "})
    assert response.status_code == 400
